terraform {
  required_version = "= 1.13.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
}

variable "blocked_endpoint" {
  type = string
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "fixture-not-a-credential"
  secret_key                  = "fixture-not-a-credential"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  max_retries                 = 0

  endpoints {
    ec2 = var.blocked_endpoint
    iam = var.blocked_endpoint
    sts = var.blocked_endpoint
  }
}

resource "aws_instance" "fixture" {
  ami           = "ami-00000000000000000"
  instance_type = "t3.micro"
  user_data     = sensitive("fixture-only-user-data")
}

resource "aws_ebs_volume" "fixture" {
  availability_zone = "us-east-1a"
  type              = "gp3"
  size              = 20
  iops              = 3000
  throughput        = 125
}

resource "aws_instance" "masked" {
  ami           = "ami-00000000000000000"
  instance_type = sensitive("t3.nano")
}

resource "terraform_data" "future" {
  input = 20
}

resource "aws_ebs_volume" "unknown" {
  availability_zone = "us-east-1a"
  type              = "gp3"
  size              = terraform_data.future.output
  iops              = 3000
  throughput        = 125
}
