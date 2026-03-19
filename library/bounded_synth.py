"""SAT-based bounded synthesis: encode 'exists k-state controller?' as SAT."""

import time
from math import ceil, log2

from pysat.solvers import Solver
from pysat.formula import CNF


def bounded_synth(automaton, inputs, outputs, k, solver_name="cd19", timeout=60):
    """Encode bounded synthesis as SAT and solve.

    Checks if there exists a k-state Mealy machine that satisfies the spec
    given by the automaton (universal co-Buchi or parity).

    Args:
        automaton: parsed HOA dict (from automata.parse_hoa)
        inputs: list of input signal names
        outputs: list of output signal names
        k: number of states to try
        solver_name: PySAT solver name ('cd19' for CaDiCaL, 'g4' for glucose4)
        timeout: seconds

    Returns dict: {sat: bool, model: list or None, time: float, k: int}
    """
    start = time.time()
    n_aut = automaton["n_states"]
    n_in = len(inputs)
    n_out = len(outputs)

    # Variable allocation
    var_count = [0]
    def new_var():
        var_count[0] += 1
        return var_count[0]

    # State variables: which automaton state maps to which controller state
    # lambda[q][s] = 1 iff automaton state q is associated with controller state s
    lam = [[new_var() for _ in range(k)] for _ in range(n_aut)]

    # Transition function: delta[s][in_val] = s' (encoded in binary)
    # Output function: out[s][in_val][o] = bool
    state_bits = max(1, ceil(log2(k))) if k > 1 else 1

    # delta[s][iv] = list of state_bits variables
    delta = {}
    for s in range(k):
        for iv in range(1 << n_in):
            delta[(s, iv)] = [new_var() for _ in range(state_bits)]

    # output function: gamma[s][iv][o]
    gamma = {}
    for s in range(k):
        for iv in range(1 << n_in):
            gamma[(s, iv)] = [new_var() for _ in range(n_out)]

    cnf = CNF()

    # Initial state: automaton start states map to controller state 0
    for q0 in automaton["start"]:
        cnf.append([lam[q0][0]])

    # At least one controller state per automaton state in the annotation
    for q in range(n_aut):
        cnf.append(lam[q])  # At least one

    # Consistency: transition relation
    # For each controller state s, input valuation iv, the output + next state
    # must be consistent with the automaton edges

    # This is a simplified encoding. The agent should improve it.
    # For now, just encode basic reachability constraints.

    elapsed = time.time() - start

    # Solve
    with Solver(name=solver_name, bootstrap_with=cnf) as solver:
        remaining = timeout - elapsed
        if remaining <= 0:
            return {"sat": None, "model": None, "time": elapsed, "k": k}

        # PySAT doesn't have native timeout for all solvers,
        # use propagation budget as approximate timeout
        sat = solver.solve()
        elapsed = time.time() - start

        if sat:
            model = solver.get_model()
            return {"sat": True, "model": model, "time": elapsed, "k": k}
        else:
            return {"sat": False, "model": None, "time": elapsed, "k": k}


def iterative_bounded_synth(spec_automaton, inputs, outputs, max_k=64, timeout=300,
                             solver_name="cd19"):
    """Try bounded synthesis with increasing k until realizable or timeout.

    Tries k = 1, 2, 4, 8, 16, 32, 64 (powers of 2).

    Args:
        spec_automaton: parsed HOA dict
        inputs, outputs: signal name lists
        max_k: maximum number of states to try
        timeout: total timeout in seconds
        solver_name: PySAT solver name

    Returns dict: {realizable: bool or None, k: int, model: list or None,
                   time: float, attempts: list}
    """
    start = time.time()
    attempts = []

    k = 1
    while k <= max_k:
        remaining = timeout - (time.time() - start)
        if remaining <= 0:
            break

        per_k_timeout = int(min(remaining, max(10, remaining / 3)))
        result = bounded_synth(
            spec_automaton, inputs, outputs, k,
            solver_name=solver_name, timeout=per_k_timeout
        )
        attempts.append({"k": k, "sat": result["sat"], "time": result["time"]})

        if result["sat"]:
            return {
                "realizable": True,
                "k": k,
                "model": result["model"],
                "time": time.time() - start,
                "attempts": attempts,
            }

        k *= 2

    return {
        "realizable": None,  # Could not determine within bounds/timeout
        "k": k // 2,
        "model": None,
        "time": time.time() - start,
        "attempts": attempts,
    }
