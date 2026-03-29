#!/bin/bash
tail -n +10 src/coreason_ecosystem/cli.py > temp_cli.py
cat << 'HEADER' > src/coreason_ecosystem/cli.py
# The Prosperity Public License 3.0.0
#
# Contributor: CoReason, Inc.
#
# Source Code: https://github.com/CoReason-AI/coreason_manifest
#
# Purpose
#
# This license allows you to use and share this software for noncommercial purposes for free and to try this software for commercial purposes for thirty days.
HEADER
cat temp_cli.py >> src/coreason_ecosystem/cli.py
rm temp_cli.py
