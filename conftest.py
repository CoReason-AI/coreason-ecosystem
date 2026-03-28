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
