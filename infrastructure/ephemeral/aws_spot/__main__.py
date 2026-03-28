# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0

import pulumi
import pulumi_aws as aws

config = pulumi.Config()
instance_type = config.require("instance_type")
ami_id = config.require("ami_id")
ssh_pub_key = config.require("ssh_pub_key")

# We can optionally create a keypair or just assume it is passed.
keypair = aws.ec2.KeyPair("spot-keypair", public_key=ssh_pub_key)

# The spot instance request
spot_instance = aws.ec2.SpotInstanceRequest(
    "fleet-spot-node",
    instance_type=instance_type,
    ami=ami_id,
    key_name=keypair.key_name,
    wait_for_fulfillment=True,
    tags={"Name": "fleet-worker-node"},
)

pulumi.export("public_ip", spot_instance.public_ip)
pulumi.export("instance_id", spot_instance.spot_instance_id)
