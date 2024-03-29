from troposphere import Base64, Join, Ref, Tags, Template
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration, Metadata
from troposphere.autoscaling import Tags as AutoScalingTags
from troposphere.cloudformation import (
    Init,
    InitConfig,
    InitFile,
    InitFiles,
    InitService,
    InitServices,
)
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.ecs import Cluster, ContainerDefinition
from troposphere.ecs import LoadBalancer as ECSLoadBalancer
from troposphere.ecs import PortMapping, Service, TaskDefinition
from troposphere.elasticloadbalancingv2 import (
    Action,
    Listener,
    LoadBalancer,
    TargetGroup,
)
from troposphere.iam import InstanceProfile, Policy, PolicyType, Role
from vars import (
    availability_zones,
    container_instances_ec2_ami_id,
    env,
    image_arn,
    instance_type,
    keyname,
    name,
    tags,
    vpc_id,
    vpc_subnets,
)

t = Template()
t.set_version("2010-09-09")


# IAM
PolicyEcr = t.add_resource(
    PolicyType(
        "PolicyEcr",
        PolicyName=f"{env}-{name}-ecr-policy",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": ["*"],
                    "Effect": "Allow",
                },
                {
                    "Action": [
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:BatchCheckLayerAvailability",
                    ],
                    "Resource": ["*"],
                    "Effect": "Allow",
                    "Sid": "AllowPull",
                },
            ],
        },
        Roles=[Ref("EcsClusterRole")],
    )
)

PolicyEcs = t.add_resource(
    PolicyType(
        "PolicyEcs",
        PolicyName=f"{env}-{name}-ecs-policy",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "ecs:CreateCluster",
                        "ecs:RegisterContainerInstance",
                        "ecs:DeregisterContainerInstance",
                        "ecs:DiscoverPollEndpoint",
                        "ecs:Submit*",
                        "ecs:Poll",
                        "ecs:StartTelemetrySession",
                    ],
                    "Resource": "*",
                    "Effect": "Allow",
                }
            ],
        },
        Roles=[Ref("EcsClusterRole")],
    )
)

PolicyCloudwatch = t.add_resource(
    PolicyType(
        "PolicyCloudwatch",
        PolicyName=f"{env}-{name}-cloudwatch-policy",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {"Action": ["cloudwatch:*"], "Resource": "*", "Effect": "Allow"}
            ],
        },
        Roles=[Ref("EcsClusterRole")],
    )
)


EcsClusterRole = t.add_resource(
    Role(
        "EcsClusterRole",
        Path="/",
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM"],
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Effect": "Allow",
                }
            ],
        },
        Policies=[
            Policy(
                PolicyName=f"{env}-{name}-ecs-service-policy",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Resource": "*",
                            "Action": [
                                "ecs:CreateCluster",
                                "ecs:DeregisterContainerInstance",
                                "ecs:DiscoverPollEndpoint",
                                "ecs:Poll",
                                "ecs:RegisterContainerInstance",
                                "ecs:StartTelemetrySession",
                                "ecs:Submit*",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Effect": "Allow",
                        }
                    ],
                },
            )
        ],
    )
)


# Container Instances
EC2InstanceProfile = t.add_resource(
    InstanceProfile(
        "EC2InstanceProfile",
        Path="/",
        Roles=[Ref("EcsClusterRole")],
    )
)


ContainerInstances = t.add_resource(
    LaunchConfiguration(
        "ContainerInstances",
        Metadata=Metadata(
            Init(
                {
                    "config": InitConfig(
                        files=InitFiles(
                            {
                                "/etc/cfn/cfn-hup.conf": InitFile(
                                    content=Join(
                                        "",
                                        [
                                            "[main]\n",
                                            "stack=",
                                            Ref("AWS::StackId"),  # NOQA
                                            "\n",
                                            "region=",
                                            Ref("AWS::Region"),
                                            "\n",
                                        ],
                                    ),  # NOQA
                                    mode="000400",
                                    owner="root",
                                    group="root",
                                ),
                                "/etc/cfn/hooks.d/cfn-auto-reloader.conf": InitFile(
                                    content=Join(
                                        "",
                                        [
                                            "[cfn-auto-reloader-hook]\n",
                                            "triggers=post.update\n",
                                            "path=Resources.ContainerInstances.Metadata.AWS::CloudFormation::Init\n",  # NOQA
                                            "action=/opt/aws/bin/cfn-init -v ",
                                            "--stack ",
                                            Ref("AWS::StackName"),  # NOQA
                                            " --resource ContainerInstances ",
                                            " --region ",
                                            Ref("AWS::Region"),
                                            "\n",  # NOQA
                                            "runas=root\n",
                                        ],
                                    ),
                                    mode="000400",
                                    owner="root",
                                    group="root",
                                ),
                            },
                        ),
                        services=InitServices(
                            {
                                "cfn-hup": InitService(
                                    ensureRunning="true",
                                    enabled="true",
                                    files=[
                                        "/etc/cfn/cfn-hup.conf",
                                        "/etc/cfn/hooks.d/cfn-auto-reloader.conf",
                                    ],
                                )
                            }
                        ),
                        commands={
                            "01_add_instance_to_cluster": {
                                "command": Join(
                                    "",
                                    [
                                        "#!/bin/bash\n",  # NOQA
                                        "echo ECS_CLUSTER=",  # NOQA
                                        Ref("ECSCluster"),  # NOQA
                                        " >> /etc/ecs/ecs.config",
                                    ],
                                )
                            },  # NOQA
                            "02_install_ssm_agent": {
                                "command": Join(
                                    "",
                                    [
                                        "#!/bin/bash\n",
                                        "yum -y update\n",  # NOQA
                                        "curl https://amazon-ssm-eu-west-1.s3.amazonaws.com/latest/linux_amd64/amazon-ssm-agent.rpm -o amazon-ssm-agent.rpm\n",  # NOQA
                                        "yum install -y amazon-ssm-agent.rpm",  # NOQA
                                    ],
                                )
                            },
                        },
                    )
                }
            ),
        ),
        UserData=Base64(
            Join(
                "",
                [
                    "#!/bin/bash -xe\n",
                    "echo ECS_CLUSTER=",
                    Ref("ECSCluster"),
                    " >> /etc/ecs/ecs.config\n",
                    "yum install -y aws-cfn-bootstrap\n",
                    "/opt/aws/bin/cfn-signal -e $? ",
                    "         --stack ",
                    Ref("AWS::StackName"),
                    "         --resource ECSAutoScalingGroup ",
                    "         --region ",
                    Ref("AWS::Region"),
                    "\n",
                ],
            )
        ),
        ImageId=container_instances_ec2_ami_id,
        KeyName=keyname,
        IamInstanceProfile=Ref("EC2InstanceProfile"),
        InstanceType=instance_type,
        AssociatePublicIpAddress="true",
    )
)


ECSAutoScalingGroup = t.add_resource(
    AutoScalingGroup(
        "ECSAutoScalingGroup",
        DesiredCapacity="1",
        MinSize="1",
        MaxSize="1",
        VPCZoneIdentifier=vpc_subnets,
        AvailabilityZones=availability_zones,
        LaunchConfigurationName=Ref("ContainerInstances"),
        TargetGroupARNs=[Ref("ALBTargetGroup")],
    )
)


# Cluster
ECSCluster = t.add_resource(Cluster("ECSCluster", Tags=Tags(**tags)))


# Service and Tasks
container_name = f"{name}-container"


ECSService = t.add_resource(
    Service(
        "ECSService",
        DependsOn=["ALBListener"],
        Cluster=Ref("ECSCluster"),
        DesiredCount=1,
        Role=Ref("ECSServiceRole"),
        LoadBalancers=[
            ECSLoadBalancer(
                ContainerName=container_name,
                ContainerPort=80,
                TargetGroupArn=Ref("ALBTargetGroup"),
            )
        ],
        TaskDefinition=Ref("ECSTaskDefinition"),
        Tags=Tags(**tags),
    )
)

ECSServiceRole = t.add_resource(
    Role(
        "ECSServiceRole",
        Path="/",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "ecs.amazonaws.com"},
                    "Effect": "Allow",
                }
            ],
        },
        Policies=[
            Policy(
                PolicyName=f"{env}-{name}-ecs-execution-task",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
                                "elasticloadbalancing:DeregisterTargets",
                                "elasticloadbalancing:Describe*",
                                "elasticloadbalancing:RegisterInstancesWithLoadBalancer",
                                "elasticloadbalancing:RegisterTargets",
                                "ec2:Describe*",
                                "ec2:AuthorizeSecurityGroupIngress",
                            ],
                            "Resource": "*",
                        }
                    ],
                },
            )
        ],
    )
)

ECSTaskDefinition = t.add_resource(
    TaskDefinition(
        "ECSTaskDefinition",
        Family=f"{env}-{name}-task-definition-family",
        ContainerDefinitions=[
            ContainerDefinition(
                "ContainerDefinition",
                Name=container_name,
                Cpu=10,
                Essential=True,
                Image=image_arn,
                Memory="512",
                PortMappings=[PortMapping(ContainerPort=80)],
            )
        ],
        Tags=Tags(**tags),
    )
)


# ALB
ApplicationLoadBalancer = t.add_resource(
    LoadBalancer("ApplicationLoadBalancer", Subnets=vpc_subnets, Tags=Tags(**tags))
)

ALBListener = t.add_resource(
    Listener(
        "ALBListener",
        DependsOn=["ECSServiceRole"],
        DefaultActions=[
            Action(
                Type="forward",
                TargetGroupArn=Ref("ALBTargetGroup"),
            )
        ],
        LoadBalancerArn=Ref("ApplicationLoadBalancer"),
        Port=80,
        Protocol="HTTP",
    )
)

ALBTargetGroup = t.add_resource(
    TargetGroup(
        "ALBTargetGroup",
        HealthCheckIntervalSeconds=30,
        HealthCheckTimeoutSeconds=5,
        HealthyThresholdCount=3,
        Port=80,
        Protocol="HTTP",
        UnhealthyThresholdCount=5,
        VpcId=vpc_id,
        Tags=Tags(**tags),
    )
)

template = t
