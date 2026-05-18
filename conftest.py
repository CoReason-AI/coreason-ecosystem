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

# Under free-threaded Python (3.13t/3.14t), skip importing bcrypt as it triggers
# segmentation faults (exit code 139) due to C-extension incompatibilities.
_is_free_threaded = (
    "free-threading" in sys.version.lower()
    or hasattr(sys.flags, "nogil")
    or sys.exec_prefix.endswith("t")
)

if _is_free_threaded:
    # Set sys.modules["bcrypt"] = None to block loading the real bcrypt C extension
    # and force it to fail with an ImportError, which cryptography/paramiko handle gracefully.
    sys.modules["bcrypt"] = None  # type: ignore[assignment]
