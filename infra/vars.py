# Config File

# Metadata
## Distinctive name to use for the whole solution
name = "tropo"

## Environment tag
env = "staging"


# EC2 Config
# Configuration to setup the EC2 instances that provide compute resources to the ECS Cluster.
## ssh keypair name to connect to the instance.
keyname = "itxaso_testing"

## Select an ECS-optimized Amazon Linux 2 instance for the region you want to use.
container_instances_ec2_ami_id = "ami-06c1d5fe67809f5dd"

## The instance type that powers the cluster.
instance_type = "t2.micro"

## The availability zones in which to setup the autoscaling group
availability_zones = ["eu-west-1a", "eu-west-1b"]


## VPC config - This template expects a VPC to be in place.
### VPC id
vpc_id = "vpc-0a6e5ca3713f4e995"

### VPC subnets - expected to be in two different availability zones (the two added above)
vpc_subnets = ["subnet-0b3594e40531d8560", "subnet-0ade85a244406b794"]


# Task Config
## ECR repo ARN to pull the image from.
ecr_repo = "324237162081.dkr.ecr.eu-west-1.amazonaws.com/hello_tropo_server"

## Image revision/tag to pull
image_tag = "0.0.1"

## Autogenerated ARN
image_arn = f"{ecr_repo}:{image_tag}"
