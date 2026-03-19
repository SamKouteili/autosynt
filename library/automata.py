"""Core automaton primitives using Spot CLI tools (ltl2tgba, autfilt)."""

import subprocess


def ltl_to_automaton(formula, aut_type="tgba", options=None):
    """Convert LTL formula to automaton using ltl2tgba.

    Args:
        formula: LTL formula string
        aut_type: 'tgba' (default), 'ba', 'monitor'
        options: additional ltl2tgba options as list

    Returns: HOA format text
    """
    cmd = ["ltl2tgba", "-f", formula]
    if aut_type == "ba":
        cmd.append("--ba")
    elif aut_type == "monitor":
        cmd.append("--monitor")
    if options:
        cmd.extend(options)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ltl2tgba failed: {result.stderr}")
    return result.stdout


def parse_hoa(text):
    """Parse HOA (Hanoi Omega-Automaton) format into Python dict.

    Returns dict with: name, n_states, start, aps (atomic propositions),
                       acceptance, edges (list of (src, dst, label, acc_sets))
    """
    lines = text.strip().split("\n")
    result = {
        "name": "",
        "n_states": 0,
        "start": [],
        "aps": [],
        "acceptance": "",
        "edges": [],
        "properties": [],
    }

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("HOA:"):
            pass
        elif line.startswith("name:"):
            result["name"] = line.split('"')[1] if '"' in line else ""
        elif line.startswith("States:"):
            result["n_states"] = int(line.split()[1])
        elif line.startswith("Start:"):
            result["start"].append(int(line.split()[1]))
        elif line.startswith("AP:"):
            parts = line.split('"')
            result["aps"] = [parts[j] for j in range(1, len(parts), 2)]
        elif line.startswith("Acceptance:"):
            result["acceptance"] = line[len("Acceptance:"):].strip()
        elif line.startswith("properties:"):
            result["properties"] = line.split()[1:]
        elif line == "--BODY--":
            i += 1
            current_state = None
            while i < len(lines) and lines[i].strip() != "--END--":
                l = lines[i].strip()
                if l.startswith("State:"):
                    parts = l.split()
                    current_state = int(parts[1])
                elif l.startswith("[") and current_state is not None:
                    # Parse edge: [label] dst {acc_sets}
                    label_end = l.index("]")
                    label = l[1:label_end]
                    rest = l[label_end + 1:].strip()
                    # Parse destination and optional acceptance sets
                    acc_sets = []
                    if "{" in rest:
                        brace_start = rest.index("{")
                        acc_str = rest[brace_start + 1:rest.index("}")]
                        acc_sets = [int(x) for x in acc_str.split() if x]
                        rest = rest[:brace_start].strip()
                    dst = int(rest)
                    result["edges"].append((current_state, dst, label, acc_sets))
                i += 1
        i += 1

    return result


def automaton_to_parity(hoa_text, options=None):
    """Convert automaton to parity acceptance using autfilt.

    Returns: HOA format text with parity acceptance
    """
    cmd = ["autfilt", "--parity=min even", "-H"]
    if options:
        cmd.extend(options)
    result = subprocess.run(
        cmd, input=hoa_text, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"autfilt failed: {result.stderr}")
    return result.stdout


def negate_formula(formula):
    """Negate an LTL formula (for unrealizability checking)."""
    return f"!({formula})"


def simplify_formula(formula):
    """Simplify LTL formula using Spot's ltlfilt."""
    result = subprocess.run(
        ["ltlfilt", "--simplify", "-f", formula],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return formula  # Return original if simplification fails
    return result.stdout.strip()


def automaton_stats(hoa_text):
    """Get statistics about an automaton using autfilt --stats."""
    result = subprocess.run(
        ["autfilt", "--stats=%s states, %e edges, %a acc-sets"],
        input=hoa_text, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return {}
    parts = result.stdout.strip().split(", ")
    stats = {}
    for p in parts:
        val, key = p.split(" ", 1)
        stats[key] = int(val)
    return stats
