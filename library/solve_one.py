"""Solve a single TLSF instance. Meant to be called as a subprocess."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from library.synth import solve_instance


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "error": "No instance name"}))
        sys.exit(1)

    instance_name = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 120

    tlsf_path = ROOT / "benchmarks" / "syntcomp-2025" / "instances" / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        print(json.dumps({"status": "error", "error": f"File not found: {tlsf_path}"}))
        sys.exit(1)

    result = solve_instance(str(tlsf_path), timeout=timeout)
    # Output JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
