"""Parse TLSF (Temporal Logic Synthesis Format) files using syfco."""

import re
import subprocess
from pathlib import Path


def parse_tlsf(filepath):
    """Parse a TLSF file and extract all relevant information.

    Returns dict with keys: formula, inputs, outputs, semantics, status, ref_size, title, description
    """
    filepath = str(filepath)

    # Get LTL formula via syfco
    formula = subprocess.run(
        ["syfco", "-f", "ltlxba", "-m", "fully", filepath],
        capture_output=True, text=True, timeout=30
    ).stdout.strip()

    # Get inputs/outputs
    inputs_str = subprocess.run(
        ["syfco", "-ins", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    outputs_str = subprocess.run(
        ["syfco", "-outs", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()

    inputs = [s.strip() for s in inputs_str.split(",") if s.strip()]
    outputs = [s.strip() for s in outputs_str.split(",") if s.strip()]

    # Get semantics
    semantics = subprocess.run(
        ["syfco", "-s", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()

    # Parse SYNTCOMP comment block for STATUS and REF_SIZE
    text = Path(filepath).read_text()
    status = "unknown"
    ref_size = -1

    syntcomp_match = re.search(r'//#!SYNTCOMP(.*?)//#\.', text, re.DOTALL)
    if syntcomp_match:
        block = syntcomp_match.group(1)
        status_match = re.search(r'STATUS\s*:\s*(\w+)', block)
        if status_match:
            status = status_match.group(1)
        ref_match = re.search(r'REF_SIZE\s*:\s*(\d+)', block)
        if ref_match:
            ref_size = int(ref_match.group(1))

    # Parse TITLE and DESCRIPTION from INFO block
    title = ""
    desc = ""
    title_match = re.search(r'TITLE:\s*"([^"]*)"', text)
    if title_match:
        title = title_match.group(1)
    desc_match = re.search(r'DESCRIPTION:\s*"([^"]*)"', text, re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()

    return {
        "formula": formula,
        "inputs": inputs,
        "outputs": outputs,
        "semantics": semantics,
        "status": status,
        "ref_size": ref_size,
        "title": title,
        "description": desc,
    }


def get_instance_stats(filepath):
    """Lightweight: just n_inputs, n_outputs, status, ref_size."""
    filepath = str(filepath)

    inputs_str = subprocess.run(
        ["syfco", "-ins", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()
    outputs_str = subprocess.run(
        ["syfco", "-outs", filepath], capture_output=True, text=True, timeout=10
    ).stdout.strip()

    n_inputs = len([s for s in inputs_str.split(",") if s.strip()])
    n_outputs = len([s for s in outputs_str.split(",") if s.strip()])

    text = Path(filepath).read_text()
    status = "unknown"
    ref_size = -1

    syntcomp_match = re.search(r'//#!SYNTCOMP(.*?)//#\.', text, re.DOTALL)
    if syntcomp_match:
        block = syntcomp_match.group(1)
        status_match = re.search(r'STATUS\s*:\s*(\w+)', block)
        if status_match:
            status = status_match.group(1)
        ref_match = re.search(r'REF_SIZE\s*:\s*(\d+)', block)
        if ref_match:
            ref_size = int(ref_match.group(1))

    return {
        "n_inputs": n_inputs,
        "n_outputs": n_outputs,
        "status": status,
        "ref_size": ref_size,
    }
