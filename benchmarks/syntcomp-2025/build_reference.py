#!/usr/bin/env python3
"""Build reference.csv for syntcomp-2025 benchmark instances."""

import os
import re
import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

INSTANCES_DIR = os.path.join(os.path.dirname(__file__), "instances")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "reference.csv")
SYFCO = "syfco"
MAX_WORKERS = 16


def extract_family(name: str) -> str:
    """Extract family from instance name using prefix before last numeric parameter."""
    # pb_N[_N...]*_pe_ pattern (parametric benchmarks)
    m = re.match(r'^(.+?)_pb_\d+(?:_\d+)*_pe_$', name)
    if m:
        return m.group(1)
    # _N suffix (digits only)
    m = re.match(r'^(.+?)_(\d+)$', name)
    if m:
        return m.group(1)
    # -N suffix
    m = re.match(r'^(.+?)-(\d+)$', name)
    if m:
        return m.group(1)
    # hex suffix _XXXXXXXX (8 hex chars)
    m = re.match(r'^(.+?)_([0-9a-f]{8})$', name)
    if m:
        return m.group(1)
    # purely numeric filename
    if re.match(r'^\d+$', name):
        return 'numeric'
    return name


def parse_syntcomp_block(content: str) -> dict:
    """Parse //#!SYNTCOMP ... //#. block from file content."""
    result = {"status": "unknown", "ref_size": -1}

    # Find the SYNTCOMP block
    block_match = re.search(r'//#!SYNTCOMP(.*?)//#\.', content, re.DOTALL)
    if not block_match:
        return result

    block = block_match.group(1)

    # Extract STATUS
    status_match = re.search(r'//STATUS\s*:\s*(\S+)', block)
    if status_match:
        result["status"] = status_match.group(1).strip()

    # Extract REF_SIZE
    ref_match = re.search(r'//REF_SIZE\s*:\s*(-?\d+)', block)
    if ref_match:
        result["ref_size"] = int(ref_match.group(1))

    return result


def count_signals(signal_str: str) -> int:
    """Count comma-separated signals, handling empty output."""
    signal_str = signal_str.strip()
    if not signal_str:
        return 0
    return len([s for s in signal_str.split(',') if s.strip()])


def run_syfco(args: list, filepath: str) -> str:
    """Run syfco with given args on filepath, return stdout stripped."""
    try:
        result = subprocess.run(
            [SYFCO] + args + [filepath],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""


def process_file(filepath: str) -> dict:
    """Process a single TLSF file and return a row dict."""
    filename = os.path.basename(filepath)
    instance = filename[:-5]  # strip .tlsf

    family = extract_family(instance)

    # Parse SYNTCOMP block from file content
    with open(filepath, 'r', errors='replace') as f:
        content = f.read()
    block_data = parse_syntcomp_block(content)

    # Run syfco commands
    ins_str = run_syfco(["-ins"], filepath)
    outs_str = run_syfco(["-outs"], filepath)
    semantics = run_syfco(["-s"], filepath)

    n_inputs = count_signals(ins_str)
    n_outputs = count_signals(outs_str)

    # Clean up semantics (may return "Mealy" or "Moore")
    if not semantics:
        semantics = "unknown"

    return {
        "instance": instance,
        "family": family,
        "status": block_data["status"],
        "ref_size": block_data["ref_size"],
        "n_inputs": n_inputs,
        "n_outputs": n_outputs,
        "semantics": semantics,
    }


def main():
    tlsf_files = sorted(
        os.path.join(INSTANCES_DIR, f)
        for f in os.listdir(INSTANCES_DIR)
        if f.endswith('.tlsf')
    )
    total = len(tlsf_files)
    print(f"Processing {total} TLSF files with {MAX_WORKERS} workers...")

    rows = []
    errors = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, fp): fp for fp in tlsf_files}
        for future in as_completed(futures):
            fp = futures[future]
            try:
                row = future.result()
                rows.append(row)
            except Exception as e:
                errors.append((fp, str(e)))
                print(f"ERROR: {fp}: {e}")
            done += 1
            if done % 100 == 0 or done == total:
                print(f"  {done}/{total} done...")

    # Sort by instance name for reproducibility
    rows.sort(key=lambda r: r["instance"])

    fieldnames = ["instance", "family", "status", "ref_size", "n_inputs", "n_outputs", "semantics"]
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {OUTPUT_CSV}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for fp, e in errors:
            print(f"  {fp}: {e}")

    # Print summary stats
    statuses = {}
    semantics_counts = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        semantics_counts[r["semantics"]] = semantics_counts.get(r["semantics"], 0) + 1

    print("\nStatus distribution:")
    for k, v in sorted(statuses.items()):
        print(f"  {k}: {v}")
    print("\nSemantics distribution:")
    for k, v in sorted(semantics_counts.items()):
        print(f"  {k}: {v}")

    families = set(r["family"] for r in rows)
    print(f"\nDistinct families: {len(families)}")
    print(f"Instances with ref_size != -1: {sum(1 for r in rows if r['ref_size'] != -1)}")


if __name__ == "__main__":
    main()
