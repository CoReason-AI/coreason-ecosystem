# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.
#

import sys
from pydantic import BaseModel

class HardwareProfile(BaseModel):
    min_vram_gb: float = 16.0
    provider_whitelist: list[str] = ["aws", "vast"]
    accelerator_type: str = "ampere"

class SecurityProfile(BaseModel):
    network_isolation: bool = True

import coreason_manifest.spec.ontology as module
module.HardwareProfile = HardwareProfile
module.SecurityProfile = SecurityProfile
