# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import base64
import pulumi
from pulumi_command import local

config = pulumi.Config()
machine_id = config.require("machine_id")
gpu_name = config.require("gpu_name")
ssh_pub_key = config.require("ssh_pub_key")
boot_payload_b64 = config.require("boot_payload_b64")

boot_payload = base64.b64decode(boot_payload_b64).decode("utf-8")

# Securely pass the complex bash script via environment variables and use data-urlencode
create_cmd = local.Command(
    "vast-create",
    create=f"curl -X POST https://console.vast.ai/api/v0/asks/{machine_id}/ -d 'client_id=auto' --data-urlencode \"ssh_key=$SSH_KEY\" --data-urlencode \"onstart=$ONSTART_PAYLOAD\"",
    delete=f"curl -X DELETE https://console.vast.ai/api/v0/instances/{machine_id}/",
    environment={
        "ONSTART_PAYLOAD": boot_payload,
        "SSH_KEY": ssh_pub_key
    }
)

pulumi.export("ssh_ip", create_cmd.stdout)
pulumi.export("ssh_port", create_cmd.stdout)
