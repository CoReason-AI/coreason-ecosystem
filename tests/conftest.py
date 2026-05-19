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
import sysconfig

# Under free-threaded Python (3.13t/3.14t), skip importing bcrypt as it triggers
# segmentation faults (exit code 139) due C-extension incompatibilities.
_is_free_threaded = (
    "free-threading" in sys.version.lower()
    or "freethreaded" in sys.version.lower()
    or hasattr(sys.flags, "nogil")
    or sys.exec_prefix.endswith("t")
    or sysconfig.get_config_var("Py_GIL_DISABLED") == 1
)

if _is_free_threaded:
    # Set sys.modules["bcrypt"] = None to block loading the real bcrypt C extension
    # and force it to fail with an ImportError, which cryptography/paramiko handle gracefully.
    sys.modules["bcrypt"] = None  # type: ignore[assignment]

try:
    from hypothesis import settings, HealthCheck
    import os

    # CI Profiles
    settings.register_profile(
        "ci-deep",
        max_examples=1000,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    settings.register_profile("default", max_examples=100, deadline=None)

    # Load default profile if set
    settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
except ImportError:
    pass
