# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import sys
from typing import Any

_is_free_threaded = (
    "free-threading" in sys.version.lower()
    or hasattr(sys.flags, "nogil")
    or sys.exec_prefix.endswith("t")
)


# Exception classes matching PyJWT's API
class InvalidTokenError(ValueError):
    pass


class ExpiredSignatureError(InvalidTokenError):
    pass


# We conditionally try to import jwt if not in free-threaded mode to keep
# with the "Borrow vs. Build" philosophy for the standard platform runtime.
if not _is_free_threaded:
    try:
        import jwt as _jwt

        _decode = _jwt.decode
        ExpiredSignatureError = _jwt.ExpiredSignatureError  # type: ignore
        InvalidTokenError = _jwt.InvalidTokenError  # type: ignore
    except ImportError:
        _jwt = None  # type: ignore
else:
    _jwt = None  # type: ignore


def decode(jwt_string: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """
    Decodes a JWT token without signature verification.
    Uses PyJWT if available, otherwise falls back to a pure-python implementation.
    """
    if _jwt is not None:
        return _decode(jwt_string, *args, **kwargs)

    raise NotImplementedError(
        "Signature verification requires PyJWT; install cryptography dependencies."
    )
