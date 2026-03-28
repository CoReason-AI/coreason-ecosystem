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
from pulumi_command import local

config = pulumi.Config()
machine_id = config.require("machine_id")
gpu_name = config.require("gpu_name")
ssh_pub_key = config.require("ssh_pub_key")

create_cmd = local.Command(
    "vast-create",
    create=f"curl -X POST https://console.vast.ai/api/v0/asks/{machine_id}/ -d 'client_id=auto' -d 'ssh_key={ssh_pub_key}'",
    delete=f"curl -X DELETE https://console.vast.ai/api/v0/instances/{machine_id}/",
)

pulumi.export("ssh_ip", create_cmd.stdout)
pulumi.export("ssh_port", create_cmd.stdout)
