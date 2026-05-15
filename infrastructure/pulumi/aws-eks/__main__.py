# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks

# 1. Create an EKS cluster for the CoReason Mesh
# By default, this uses the BYOO standard, allowing horizontal scale of the Governance Plane.
cluster = eks.Cluster(
    "coreason-mesh-cluster",
    instance_type="t3.medium",
    desired_capacity=2,
    min_size=1,
    max_size=5,
)

# 2. Export the cluster kubeconfig
pulumi.export("kubeconfig", cluster.kubeconfig)
