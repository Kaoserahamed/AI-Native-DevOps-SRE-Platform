"""Export the versioned platform contract schemas.

Usage:
    python scripts/export_contract_schemas.py            # (re)write the committed schemas
    python scripts/export_contract_schemas.py --check    # fail when the committed schemas are stale

``--check`` is what the contract test tier runs, so a schema change without an intentional snapshot
update fails CI instead of drifting silently.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from packages.contracts.versioning import (
    CONTRACT_MODELS,
    export_schemas,
    schema_differences,
    schema_snapshot_directory,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: Sequence[str] | None = None) -> int:
    """Run the exporter in write mode or verify mode."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root holding packages/")
    parser.add_argument(
        "--check", action="store_true", help="verify the committed schemas match the code"
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    directory = schema_snapshot_directory(root)

    if args.check:
        differences = schema_differences(directory)
        if differences:
            for difference in differences:
                print(f"  - {difference}")
            print(f"contract schema check failed with {len(differences)} difference(s)")
            return 1
        print(f"contract schemas are current ({len(CONTRACT_MODELS)} documents)")
        return 0

    written = export_schemas(directory)
    print(f"wrote {len(written)} contract schema(s) to {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
