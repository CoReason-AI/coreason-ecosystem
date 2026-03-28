from unittest.mock import MagicMock
import sys

# We need to mock coreason_manifest.spec.ontology for the tests to pass since the
# pip version of coreason_manifest might not have these attributes.

module = MagicMock()
sys.modules['coreason_manifest.spec.ontology'] = module

class HardwareProfile(MagicMock):
    min_vram_gb: float = 16.0
    provider_whitelist: list[str] = ["aws", "vast"]
    accelerator_type: str = "ampere"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

class SecurityProfile(MagicMock):
    network_isolation: bool = True
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

module.HardwareProfile = HardwareProfile
module.SecurityProfile = SecurityProfile
