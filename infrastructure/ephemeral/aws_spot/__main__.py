# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.

import pulumi
import pulumi_aws as aws

config = pulumi.Config()
instance_type = config.require("instance_type")
ami_id = config.require("ami_id")
ssh_pub_key = config.require("ssh_pub_key")

key_pair = aws.ec2.KeyPair("spot-key", public_key=ssh_pub_key)

spot_instance_request = aws.ec2.SpotInstanceRequest(
    "spot-instance",
    ami=ami_id,
    instance_type=instance_type,
    key_name=key_pair.key_name,
    wait_for_fulfillment=True,
    spot_type="one-time",
)

pulumi.export("public_ip", spot_instance_request.public_ip)
pulumi.export("instance_id", spot_instance_request.id)
