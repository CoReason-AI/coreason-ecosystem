# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0

import json
import pulumi
import pulumi_command

config = pulumi.Config()
machine_id = config.require("machine_id")
gpu_name = config.require("gpu_name")
ssh_pub_key = config.require("ssh_pub_key")

# For Vast.ai, as there's no native provider, we'll wrap a cURL command
# using pulumi_command.local.Command.
# Note: This is an ephemeral template designed to be driven dynamically.

create_command = f"""
echo 'Simulating vast.ai machine rental for machine_id={machine_id}, gpu={gpu_name}'
# In reality, this would be a curl command against the vast.ai API, e.g.:
# curl -X PUT https://console.vast.ai/api/v0/asks/{machine_id}/ \\
#      -d '{{\"client_id\":\"me\",\"ssh_key\":\"{ssh_pub_key}\"}}'
echo '{{"ssh_ip": "192.168.1.100", "ssh_port": "22000"}}'
"""

destroy_command = f"""
echo 'Simulating vast.ai machine destruction for machine_id={machine_id}'
# curl -X DELETE https://console.vast.ai/api/v0/instances/{machine_id}/
"""

vast_rent = pulumi_command.local.Command(
    "vast-rent-node",
    create=create_command,
    delete=destroy_command,
    environment={"MACHINE_ID": machine_id, "SSH_KEY": ssh_pub_key},
)

# Parse the simulated output
# A real implementation would parse the vast API JSON response.
parsed_output = vast_rent.stdout.apply(
    lambda stdout: json.loads(stdout.strip().split("\n")[-1])
)

pulumi.export("ssh_ip", parsed_output.apply(lambda out: out.get("ssh_ip")))
pulumi.export("ssh_port", parsed_output.apply(lambda out: out.get("ssh_port")))
