"""AIGER circuit handling for reactive synthesis output."""

import subprocess


def mealy_to_aiger(mealy, inputs, outputs):
    """Encode a Mealy machine as an AIGER circuit (ASCII aag format).

    This is a placeholder that produces a simple encoding.
    The agent should improve this with better encodings and minimization.

    Args:
        mealy: dict with states, initial, transitions
        inputs: list of input signal names
        outputs: list of output signal names

    Returns: AIGER text in aag format
    """
    n_states = len(mealy["states"])
    if n_states == 0:
        # Trivial: no states, constant outputs
        n_in = len(inputs)
        n_out = len(outputs)
        lines = [f"aag {n_in} {n_in} 0 {n_out} 0"]
        for i in range(n_in):
            lines.append(str(2 * (i + 1)))
        for _ in range(n_out):
            lines.append("0")  # constant false
        for name in inputs:
            lines.append(f"i{inputs.index(name)} {name}")
        for i, name in enumerate(outputs):
            lines.append(f"o{i} {name}")
        return "\n".join(lines) + "\n"

    # State bits needed
    import math
    n_state_bits = max(1, math.ceil(math.log2(n_states))) if n_states > 1 else 1
    n_in = len(inputs)
    n_out = len(outputs)
    n_latches = n_state_bits

    # Placeholder: generate a minimal valid AIGER
    # Real implementation should encode the transition/output functions as AND gates
    max_var = n_in + n_latches
    lines = [f"aag {max_var} {n_in} {n_latches} {n_out} 0"]

    # Inputs
    for i in range(n_in):
        lines.append(str(2 * (i + 1)))

    # Latches: lit next_lit (initially 0)
    for i in range(n_latches):
        latch_var = n_in + 1 + i
        lines.append(f"{2 * latch_var} 0")  # Next state = 0 (placeholder)

    # Outputs (placeholder: all false)
    for _ in range(n_out):
        lines.append("0")

    # Symbol table
    for i, name in enumerate(inputs):
        lines.append(f"i{i} {name}")
    for i in range(n_latches):
        lines.append(f"l{i} state_{i}")
    for i, name in enumerate(outputs):
        lines.append(f"o{i} {name}")

    return "\n".join(lines) + "\n"


def parse_aiger(text):
    """Parse AIGER format (aag ASCII) into Python structure.

    Returns dict with: max_var, n_inputs, n_latches, n_outputs, n_ands,
                       inputs, latches, outputs, ands, symbols
    """
    lines = text.strip().split("\n")
    header = lines[0].split()

    result = {
        "format": header[0],
        "max_var": int(header[1]),
        "n_inputs": int(header[2]),
        "n_latches": int(header[3]),
        "n_outputs": int(header[4]),
        "n_ands": int(header[5]),
        "inputs": [],
        "latches": [],
        "outputs": [],
        "ands": [],
        "symbols": {},
    }

    idx = 1
    for _ in range(result["n_inputs"]):
        result["inputs"].append(int(lines[idx]))
        idx += 1
    for _ in range(result["n_latches"]):
        parts = lines[idx].split()
        result["latches"].append((int(parts[0]), int(parts[1])))
        idx += 1
    for _ in range(result["n_outputs"]):
        result["outputs"].append(int(lines[idx]))
        idx += 1
    for _ in range(result["n_ands"]):
        parts = lines[idx].split()
        result["ands"].append((int(parts[0]), int(parts[1]), int(parts[2])))
        idx += 1

    # Parse symbol table
    while idx < len(lines):
        line = lines[idx]
        if line.startswith(("i", "l", "o")) and " " in line:
            kind_idx, name = line.split(" ", 1)
            result["symbols"][kind_idx] = name
        elif line.startswith("c"):
            break  # Comment section
        idx += 1

    return result


def aiger_stats(text):
    """Extract AND gate count, latches, and other stats from AIGER text."""
    parsed = parse_aiger(text)
    return {
        "and_gates": parsed["n_ands"],
        "latches": parsed["n_latches"],
        "inputs": parsed["n_inputs"],
        "outputs": parsed["n_outputs"],
        "max_var": parsed["max_var"],
    }


def validate_circuit(aiger_path, tlsf_path, timeout=60):
    """Validate an AIGER circuit against a TLSF specification.

    Uses ltlsynt --verify or a model checker to verify correctness.
    Returns (valid, message) tuple.
    """
    # Use ltlsynt --realizability to check, or nuXmv if available
    # For now, use a basic approach with Spot tools
    try:
        result = subprocess.run(
            ["ltlsynt", "--verify-aiger=" + str(aiger_path), str(tlsf_path)],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return True, "Valid"
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Verification timed out"
    except Exception as e:
        return False, str(e)


def ltlsynt_solve(tlsf_path, timeout=300):
    """Run ltlsynt on a TLSF file as baseline.

    Returns dict with: realizable (bool), aiger (str or None), time (float)
    """
    import time
    start = time.time()
    try:
        result = subprocess.run(
            ["ltlsynt", "--tlsf=" + str(tlsf_path), "--aiger"],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.time() - start

        output = result.stdout.strip()
        if "REALIZABLE" in output and "UNREALIZABLE" not in output:
            # Extract AIGER after "REALIZABLE\n"
            parts = output.split("\n", 1)
            aiger = parts[1] if len(parts) > 1 else None
            return {"realizable": True, "aiger": aiger, "time": elapsed}
        elif "UNREALIZABLE" in output:
            return {"realizable": False, "aiger": None, "time": elapsed}
        else:
            return {"realizable": None, "aiger": None, "time": elapsed}
    except subprocess.TimeoutExpired:
        return {"realizable": None, "aiger": None, "time": timeout}
