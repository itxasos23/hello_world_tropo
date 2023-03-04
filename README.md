# Tropo Server

A simple project to display "Welcome to the Cloud Platform Team" via AWS ECS.

This project has two main folders:
- `infra`: Contains the Python code to create the [AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) template via [Troposphere](https://troposphere.readthedocs.io/en/latest/index.html).
- `server`: Contains the [nginx](https://nginx.org/en/) server that exposes the static html file showing the expected message.

The `infra` section is configurable via the parameters set in `infra/vars.py` file.


Future work/Nice to haves:
- Usability:
  - Refactor to accept different parameter setting (python arguments, env vars, etc.)
  - Add output options (direct to file, to std_out, `yaml` vs. `json`, etc.)
  - Add parameter validation (maybe even checking for existence; e.g. check that a given keypair exists via `aws cli` before building the template).

- AutoScaling:
  - ECS Container Instances AutoScaling based on average Host CPU usage.
  - ECS Service Tasks AutoScaling based on average Container CPU usage.
  - Parametrize AutoScaling configuration.

- Reusability:
  - Add mapping for AMI selection and availability zone selection based on AWS Region.


## Infra

This project creates the following resources:

- ECS Cluster:
    - ECS Service: AutoScaling is not configured for this service; TaskCount hardcoded to 1 Task.
        - ECS TaskDefinition:
    - ALBv2:
        - ALB Listener
        - ALB TargetGroup: ECS Service assigned to the TargetGroup
    - ECS ContainerInstances:
        - EC2 AutoScaling Group: Auto Scaling is not configured; InstanceCount hardcoded to 1 Instance.


Crucially, this project expects the following resources to be present.
This is intentional, as many companies have a main VPC configuration that gets imported into the project via IDs.
- VPC:
    - VPC:
    - Subnets: Split into two availability zones.
    - Internet Gateway: Needed to expose the ALBv2 Listener.

(other resources, like IAM, omitted for brevity)


## Deployment

Deployment has **three** stages:
1. **Build and push** the `tropo` image to ECR.
2. **Build** the AWS CloudFormation **template** with Troposphere.
3. **Create the AWS CloudFormation Stack** from the template created in step 2.


### Build and push the `tropo` image to ECR

The `tropo` image is a simple nginx server with a static HTML file on its root.

Pushing a container image to a remote ECR repo requires some setup, [check the docs](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html) if you're stuck.

To build the image:

1. Clone the repo.

> `git clone <this repo>`

2. `cd` into the `server` directory.

> `cd server`

3. Build and tag the image with Docker.

> `docker build . -t <ecr-repo-name>:<image-tag`

e.g.

> `docker build . -t tropo:0.0.1`

4. Push the image

> `docker push <aws-account-id>.dkr.ecr.<aws-region>.amazonaws.com/<ecr-repo-name>:<image-tag>`

e.g.

> `docker push 0000000000.dkr.ecr.eu-west-1.amazonaws.com/tropo:0.0.1`


### Build the AWS CloudFormation template

To build the AWS CloudFormation template, add your desired parameters in `infra/vars.py` and invoke the `infra/main.py` script.
`infra/main.py` will output the template to `stdout`. 

Follow these steps to build the template to a file:
1. review the variables in `infra/vars.py`

> `cat infra/vars.py`

2. Setup your python environment:
  a. Setup an environment with python 3.11.0 (e.g. with [pyenv](https://github.com/pyenv/pyenv))

> `pyenv virtualenv 3.11.0 tropo_dev`

> `pyenv local tropo_dev`

  b. Install dependencies from `requirements.txt`

> `pip install -r requirements.txt`

3. Invoke the `infra/main.py` script and pipe it to a file.

> `python infra/main.py > output/tropo_out.yml`


### Create the AWS CloudFormation Stack

Now that we have local `json` or `yaml` file with the desired resources, we need to create the AWS CloudFormation Stack.
Choose a semantic name for the stack (e.g. `tropo-ecs-server`), identify the template location and add the `IAM` capability.

> `aws cloudformation create-stack --stack-name <stack-name> --template-body file://<relative-path-to-template> --capabilities CAPABILITY_IAM`

e.g.

> `aws cloudformation create-stack --stack-name tropo-ecs-server --template-body file://output/tropo_out.yaml --capabilities CAPABILITY_IAM`

