# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""
coreason-ecosystem: The Governance Plane.

This package provides the stateless substrate and macroscopic orchestrator for the
CoReason Tripartite Cybernetic Manifold. It implements the Hollow Plane doctrine,
governing cryptographic identity (SPIFFE/SPIRE), epistemic risk quarantine, and
thermodynamic infrastructure actuation (Pulumi).

Part of the CoReason Tripartite Cybernetic Manifold.
"""

__version__ = "0.11.1"
__author__ = "Gowtham A Rao"
__email__ = "gowtham.rao@coreason.ai"

from .cli import main

__all__ = ["main"]
