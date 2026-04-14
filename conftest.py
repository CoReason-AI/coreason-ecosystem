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
from unittest.mock import MagicMock
from pydantic_core import core_schema

class _MockOntologyModel(MagicMock):
    """Dynamic constructor for mocked ontology parameters to fix test duck-typing faults."""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.any_schema()

    def __init__(self, **kwargs):
        super().__init__()
        for k, v in kwargs.items():
            setattr(self, k, v)


mock_ontology = MagicMock()
mock_ontology.HardwareProfile = _MockOntologyModel
mock_ontology.SecurityProfile = _MockOntologyModel
mock_ontology.CoreasonBaseState = _MockOntologyModel

sys.modules["coreason_manifest.spec.ontology"] = mock_ontology
