# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Pulumi Mainnet Infrastructure: Multi-Region High Availability.

Defines the Tier-0 baseline infrastructure for the CoReason Mainnet
across globally distributed regions. Provisions managed databases,
Kubernetes/ECS clusters for core adjudicator nodes, Temporal workers,
and injects the network_bootstrap.json as a secure secret.
"""

from __future__ import annotations

import json
from pathlib import Path

import pulumi
import pulumi_aws as aws


# ── Configuration ──────────────────────────────────────────────────────

config = pulumi.Config("coreason")

REGIONS = ["us-east-1", "eu-central-1"]
PROJECT_NAME = "coreason-mainnet"
ENVIRONMENT = config.get("environment") or "production"

# Load bootstrap config if available
BOOTSTRAP_PATH = Path("./network_bootstrap.json")
BOOTSTRAP_CONFIG: dict = {}
if BOOTSTRAP_PATH.exists():
    BOOTSTRAP_CONFIG = json.loads(BOOTSTRAP_PATH.read_text(encoding="utf-8"))


# ── VPC & Networking ───────────────────────────────────────────────────


def create_vpc(region_name: str) -> dict:
    """Create a VPC with public and private subnets for a region."""
    vpc = aws.ec2.Vpc(
        f"{PROJECT_NAME}-vpc-{region_name}",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={
            "Name": f"{PROJECT_NAME}-vpc-{region_name}",
            "Environment": ENVIRONMENT,
            "ManagedBy": "pulumi",
        },
    )

    # Public subnet for load balancers and ingress
    public_subnet = aws.ec2.Subnet(
        f"{PROJECT_NAME}-public-{region_name}",
        vpc_id=vpc.id,
        cidr_block="10.0.1.0/24",
        map_public_ip_on_launch=True,
        tags={"Name": f"{PROJECT_NAME}-public-{region_name}"},
    )

    # Private subnet for compute and databases
    private_subnet = aws.ec2.Subnet(
        f"{PROJECT_NAME}-private-{region_name}",
        vpc_id=vpc.id,
        cidr_block="10.0.2.0/24",
        map_public_ip_on_launch=False,
        tags={"Name": f"{PROJECT_NAME}-private-{region_name}"},
    )

    # Internet Gateway for public subnet
    igw = aws.ec2.InternetGateway(
        f"{PROJECT_NAME}-igw-{region_name}",
        vpc_id=vpc.id,
        tags={"Name": f"{PROJECT_NAME}-igw-{region_name}"},
    )

    return {
        "vpc": vpc,
        "public_subnet": public_subnet,
        "private_subnet": private_subnet,
        "igw": igw,
    }


# ── Security Groups ───────────────────────────────────────────────────


def create_security_groups(vpc_id: pulumi.Output, region_name: str) -> dict:
    """Create security groups for the mainnet components."""
    # Temporal worker security group
    temporal_sg = aws.ec2.SecurityGroup(
        f"{PROJECT_NAME}-temporal-sg-{region_name}",
        vpc_id=vpc_id,
        description="Security group for Temporal workers",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=7233,
                to_port=7233,
                cidr_blocks=["10.0.0.0/16"],
                description="Temporal gRPC",
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
                description="All outbound",
            ),
        ],
        tags={"Name": f"{PROJECT_NAME}-temporal-sg-{region_name}"},
    )

    # Federation ingress security group (public-facing)
    ingress_sg = aws.ec2.SecurityGroup(
        f"{PROJECT_NAME}-ingress-sg-{region_name}",
        vpc_id=vpc_id,
        description="Security group for Federation Ingress Gateway",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=443,
                to_port=443,
                cidr_blocks=["0.0.0.0/0"],
                description="HTTPS/mTLS ingress",
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
                description="All outbound",
            ),
        ],
        tags={"Name": f"{PROJECT_NAME}-ingress-sg-{region_name}"},
    )

    return {
        "temporal_sg": temporal_sg,
        "ingress_sg": ingress_sg,
    }


# ── ECS Cluster & Services ────────────────────────────────────────────


def create_ecs_cluster(region_name: str, private_subnet_id: pulumi.Output) -> dict:
    """Create an ECS cluster for core adjudicator nodes."""
    cluster = aws.ecs.Cluster(
        f"{PROJECT_NAME}-cluster-{region_name}",
        settings=[
            aws.ecs.ClusterSettingArgs(
                name="containerInsights",
                value="enabled",
            )
        ],
        tags={
            "Name": f"{PROJECT_NAME}-cluster-{region_name}",
            "Environment": ENVIRONMENT,
        },
    )

    # Temporal worker task definition
    temporal_task = aws.ecs.TaskDefinition(
        f"{PROJECT_NAME}-temporal-task-{region_name}",
        family=f"{PROJECT_NAME}-temporal-worker",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu="1024",
        memory="2048",
        container_definitions=json.dumps(
            [
                {
                    "name": "temporal-worker",
                    "image": "coreason/runtime-worker:latest",
                    "cpu": 1024,
                    "memory": 2048,
                    "essential": True,
                    "portMappings": [{"containerPort": 7233, "protocol": "tcp"}],
                    "environment": [
                        {"name": "COREASON_ENV", "value": ENVIRONMENT},
                        {"name": "TEMPORAL_NAMESPACE", "value": "coreason-mainnet"},
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/ecs/{PROJECT_NAME}-temporal",
                            "awslogs-region": region_name,
                            "awslogs-stream-prefix": "temporal",
                        },
                    },
                }
            ]
        ),
        tags={"Name": f"{PROJECT_NAME}-temporal-task-{region_name}"},
    )

    # Federation ingress task definition
    ingress_task = aws.ecs.TaskDefinition(
        f"{PROJECT_NAME}-ingress-task-{region_name}",
        family=f"{PROJECT_NAME}-federation-ingress",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu="512",
        memory="1024",
        container_definitions=json.dumps(
            [
                {
                    "name": "federation-ingress",
                    "image": "coreason/federation-ingress:latest",
                    "cpu": 512,
                    "memory": 1024,
                    "essential": True,
                    "portMappings": [{"containerPort": 443, "protocol": "tcp"}],
                    "environment": [
                        {"name": "COREASON_ENV", "value": ENVIRONMENT},
                        {"name": "RATE_LIMIT_PER_MINUTE", "value": "30"},
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/ecs/{PROJECT_NAME}-ingress",
                            "awslogs-region": region_name,
                            "awslogs-stream-prefix": "ingress",
                        },
                    },
                }
            ]
        ),
        tags={"Name": f"{PROJECT_NAME}-ingress-task-{region_name}"},
    )

    return {
        "cluster": cluster,
        "temporal_task": temporal_task,
        "ingress_task": ingress_task,
    }


# ── Secrets Management ────────────────────────────────────────────────


def inject_bootstrap_secret(region_name: str) -> aws.secretsmanager.Secret:
    """Inject the network_bootstrap.json as a secure secret."""
    secret = aws.secretsmanager.Secret(
        f"{PROJECT_NAME}-bootstrap-{region_name}",
        description="CoReason Mainnet bootstrap configuration",
        tags={
            "Name": f"{PROJECT_NAME}-bootstrap-{region_name}",
            "Environment": ENVIRONMENT,
        },
    )

    aws.secretsmanager.SecretVersion(
        f"{PROJECT_NAME}-bootstrap-version-{region_name}",
        secret_id=secret.id,
        secret_string=json.dumps(BOOTSTRAP_CONFIG),
    )

    return secret


# ── Main Infrastructure Composition ───────────────────────────────────

regional_outputs: dict[str, dict] = {}

for region in REGIONS:
    # VPC
    vpc_resources = create_vpc(region)

    # Security Groups
    sg_resources = create_security_groups(vpc_resources["vpc"].id, region)

    # ECS Cluster
    ecs_resources = create_ecs_cluster(region, vpc_resources["private_subnet"].id)

    # Secrets
    bootstrap_secret = inject_bootstrap_secret(region)

    regional_outputs[region] = {
        "vpc_id": vpc_resources["vpc"].id,
        "cluster_arn": ecs_resources["cluster"].arn,
        "bootstrap_secret_arn": bootstrap_secret.arn,
    }

# ── Pulumi Exports ────────────────────────────────────────────────────

for region, outputs in regional_outputs.items():
    pulumi.export(f"{region}_vpc_id", outputs["vpc_id"])
    pulumi.export(f"{region}_cluster_arn", outputs["cluster_arn"])
    pulumi.export(f"{region}_bootstrap_secret_arn", outputs["bootstrap_secret_arn"])

pulumi.export("regions", REGIONS)
pulumi.export("environment", ENVIRONMENT)
pulumi.export("project", PROJECT_NAME)
