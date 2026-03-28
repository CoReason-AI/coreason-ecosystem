# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-manifest>

import base64
import pulumi
import pulumi_aws as aws

config = pulumi.Config()
instance_type = config.require("instance_type")
ami_id = config.require("ami_id")
ssh_pub_key = config.require("ssh_pub_key")
boot_payload_b64 = config.require("boot_payload_b64")

boot_payload = base64.b64decode(boot_payload_b64).decode("utf-8")

key_pair = aws.ec2.KeyPair("spot-key", public_key=ssh_pub_key)

spot_instance_request = aws.ec2.SpotInstanceRequest(
    "spot-instance",
    ami=ami_id,
    instance_type=instance_type,
    key_name=key_pair.key_name,
    user_data=boot_payload,
    wait_for_fulfillment=True,
    spot_type="one-time",
)

pulumi.export("public_ip", spot_instance_request.public_ip)
pulumi.export("instance_id", spot_instance_request.id)
