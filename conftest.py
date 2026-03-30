# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import sys
from pydantic import BaseModel

class HardwareProfile(BaseModel):
    min_vram_gb: float = 16.0
    provider_whitelist: list[str] = ["aws", "vast"]
    accelerator_type: str = "ampere"

class SecurityProfile(BaseModel):
    network_isolation: bool = True

import sys; sys.modules["coreason_manifest.spec.ontology"] = sys.modules[__name__]
