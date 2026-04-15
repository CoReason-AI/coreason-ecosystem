"""
Validate the epistemic integrity of the registry lockfile.
"""

import sys
import json
import re
from pathlib import Path


def validate() -> None:
    lock_path = Path(".coreason/registry.lock")
    if not lock_path.exists():
        print("Registry lockfile not found. Assuming clean state.")
        sys.exit(0)

    try:
        content = lock_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"ERROR: Registry lockfile is not valid JSON:\n{e}")
        sys.exit(1)

    if "epistemic_root" not in data:
        print("ERROR: Missing 'epistemic_root' in registry lockfile.")
        sys.exit(1)

    root_hash = data["epistemic_root"]

    # Check SHA-256 validity
    if not isinstance(root_hash, str) or not re.match(r"^[a-fA-F0-9]{64}$", root_hash):
        print(f"ERROR: Invalid SHA-256 hash format for epistemic_root: {root_hash}")
        sys.exit(1)

    from typing import Any

    def dict_raise_on_duplicates(
        ordered_pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        d = {}
        for k, v in ordered_pairs:
            if k in d:
                raise ValueError(f"Duplicate key found: {k}")
            d[k] = v
        return d

    try:
        json.loads(content, object_pairs_hook=dict_raise_on_duplicates)
    except ValueError as e:
        print(f"ERROR: Malformed registry lockfile: {e}")
        sys.exit(1)

    print(f"Registry lockfile integrity validated. Epistemic Root: {root_hash}")
    sys.exit(0)


if __name__ == "__main__":
    validate()
