"""Core-guided MaxSAT solver for instances with unit soft clauses.

Uses SAT solver assumptions to iteratively find and relax unsatisfiable cores.
Only works when all soft clauses are unit (single literal). For such instances,
this is dramatically more effective than local search — e.g. timetabling comp07.lp
went from 1778x to optimal.
"""

import time

from pysat.solvers import Solver
try:
    from library.wcnf_parser import evaluate_cost
    from library.solvers import sat_solve_with_timeout, SolverTimeout
except ImportError:
    from wcnf_parser import evaluate_cost
    from solvers import sat_solve_with_timeout, SolverTimeout


def core_guided_solve(nvars, hard_clauses, soft_clauses, timeout=240, solver_name='cd19'):
    """Naive core-guided solver — excludes all core literals. Fast but suboptimal."""
    soft_lits = []
    for w, clause in soft_clauses:
        if len(clause) != 1:
            return None, None
        soft_lits.append((w, clause[0]))

    soft_lits.sort(key=lambda x: x[0], reverse=True)
    t0 = time.time()

    with Solver(name=solver_name) as sat:
        for clause in hard_clauses:
            sat.add_clause(clause)

        excluded = set()
        best_sol = None
        best_cost = float('inf')

        while time.time() - t0 < timeout:
            assumptions = [lit for _, lit in soft_lits if lit not in excluded]
            remaining = max(1, int(timeout - (time.time() - t0)))
            try:
                result = sat_solve_with_timeout(sat, assumptions=assumptions, timeout=remaining)
            except SolverTimeout:
                break
            if result:
                model = sat.get_model()
                sol = [lit for lit in model if abs(lit) <= nvars]
                present = set(abs(lit) for lit in sol)
                for v in range(1, nvars + 1):
                    if v not in present:
                        sol.append(v)
                cost = evaluate_cost(sol, soft_clauses)
                if cost < best_cost:
                    best_cost = cost
                    best_sol = sol
                break
            else:
                core = sat.get_core()
                if not core:
                    break
                excluded.update(core)

    return best_sol, best_cost


def core_guided_budget(nvars, hard_clauses, soft_clauses, timeout=60,
                       solver_name='cd19', conf_budget=100000):
    """Core-guided solver with conflict budget — handles hard SAT instances.

    When a SAT call exceeds the conflict budget, drops the lightest remaining
    assumption instead of hanging. This is dramatically more effective than
    naive core-guided on instances where some SAT calls hang (e.g. synplicate).

    Game-changer results:
    - synplicate size11 arity3/f3: 535→194 (4.25x→1.54x)
    - synplicate dag_run2_16: 819→333 (2.06x→0.84x, BEATS REFERENCE)
    """
    soft_lits = []
    for w, clause in soft_clauses:
        if len(clause) != 1:
            return None, None
        soft_lits.append((w, clause[0]))

    soft_lits.sort(key=lambda x: x[0], reverse=True)
    t0 = time.time()

    with Solver(name=solver_name) as sat:
        for clause in hard_clauses:
            sat.add_clause(clause)

        excluded = set()
        best_sol = None
        best_cost = float('inf')

        for iteration in range(len(soft_lits) * 2):
            if time.time() - t0 > timeout:
                break
            assumptions = [lit for _, lit in soft_lits if lit not in excluded]
            if not assumptions:
                break

            sat.conf_budget(conf_budget)
            result = sat.solve_limited(assumptions=assumptions, expect_interrupt=True)

            if result is True:
                model = sat.get_model()
                sol = [lit for lit in model if abs(lit) <= nvars]
                present = set(abs(lit) for lit in sol)
                for v in range(1, nvars + 1):
                    if v not in present:
                        sol.append(v)
                cost = evaluate_cost(sol, soft_clauses)
                if cost < best_cost:
                    best_cost = cost
                    best_sol = sol
                break
            elif result is False:
                core = sat.get_core()
                if not core:
                    break
                excluded.update(core)
            else:
                # Budget exceeded — drop lightest remaining assumption
                remaining = [(w, lit) for w, lit in soft_lits if lit not in excluded]
                if not remaining:
                    break
                _, lightest = min(remaining, key=lambda x: x[0])
                excluded.add(lightest)

    return best_sol, best_cost


def wpm1_solve(nvars, hard_clauses, soft_clauses, timeout=240, solver_name='cd19'):
    """WPM1-style core-guided solver with proper relaxation variables.

    Instead of excluding all core literals (naive approach), adds relaxation:
    - For each core, find min weight and subtract from all core members
    - Add at-most-one relaxation constraint
    - Zero-weight assumptions are removed

    Much better quality than naive core-guided, especially for weighted instances.
    """
    soft_lits = []
    for w, clause in soft_clauses:
        if len(clause) != 1:
            return None, None
        soft_lits.append((w, clause[0]))

    t0 = time.time()
    next_var = nvars + 1

    with Solver(name=solver_name) as sat:
        for clause in hard_clauses:
            sat.add_clause(clause)

        # Active assumptions: {assumption_lit: weight}
        active = {}
        for w, lit in soft_lits:
            if lit in active:
                active[lit] = active[lit] + w
            else:
                active[lit] = w

        lower_bound = 0
        best_sol = None
        best_cost = float('inf')
        iterations = 0

        while time.time() - t0 < timeout:
            iterations += 1
            assumptions = list(active.keys())

            if sat.solve(assumptions=assumptions):
                model = sat.get_model()
                sol = [lit for lit in model if abs(lit) <= nvars]
                present = set(abs(lit) for lit in sol)
                for v in range(1, nvars + 1):
                    if v not in present:
                        sol.append(v)
                cost = evaluate_cost(sol, soft_clauses)
                if cost < best_cost:
                    best_cost = cost
                    best_sol = sol
                break
            else:
                core = sat.get_core()
                if not core:
                    break
                core_set = set(core)

                # Find minimum weight in core
                min_w = min(active[lit] for lit in core if lit in active)
                lower_bound += min_w

                # Relaxation variables for this core
                relax_vars = []
                for lit in core:
                    if lit not in active:
                        continue
                    w = active[lit]
                    del active[lit]

                    remaining_w = w - min_w
                    if remaining_w > 0:
                        # Split: keep original lit with remaining weight
                        active[lit] = remaining_w

                    # Create relaxation variable
                    r = next_var
                    next_var += 1
                    relax_vars.append(r)

                    # lit OR r must be true (if lit is falsified, r must be true)
                    sat.add_clause([lit, r])

                # At most one relaxation variable can be true (exactly one lit in core is relaxed)
                # Encode as: at-least-one + pairwise at-most-one
                if len(relax_vars) > 1:
                    # At least one relaxation (the core says at least one assumption must be false)
                    sat.add_clause(relax_vars)
                    # Pairwise at-most-one (for small cores)
                    if len(relax_vars) <= 20:
                        for i in range(len(relax_vars)):
                            for j in range(i + 1, len(relax_vars)):
                                sat.add_clause([-relax_vars[i], -relax_vars[j]])
                    else:
                        # For large cores, use sequential counter encoding
                        _encode_at_most_one_sequential(sat, relax_vars, next_var)
                        next_var += len(relax_vars) - 1
                elif len(relax_vars) == 1:
                    sat.add_clause(relax_vars)

    return best_sol, best_cost


def _encode_at_most_one_sequential(sat, lits, start_var):
    """Encode at-most-one constraint using sequential counter (linear clauses)."""
    n = len(lits)
    if n <= 1:
        return
    # Auxiliary vars: s_1, ..., s_{n-1}
    s = [start_var + i for i in range(n - 1)]
    # x_0 => s_0
    sat.add_clause([-lits[0], s[0]])
    for i in range(1, n - 1):
        # x_i => s_i
        sat.add_clause([-lits[i], s[i]])
        # s_{i-1} => s_i
        sat.add_clause([-s[i - 1], s[i]])
        # x_i and s_{i-1} can't both be true
        sat.add_clause([-lits[i], -s[i - 1]])
    # x_{n-1} and s_{n-2} can't both be true
    sat.add_clause([-lits[n - 1], -s[n - 2]])
