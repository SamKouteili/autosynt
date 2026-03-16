- wcnf_parser.py:
    - parse_wcnf: parse a WCNF (2022+ format) file into hard clauses, soft clauses with weights, and metadata
    - evaluate_cost: compute MaxSAT cost (sum of weights of unsatisfied soft clauses) for a given assignment
    - check_hard_clauses: check which hard clauses a given assignment violates

- solutions.py:
    - load_solutions: load all best solutions from best-solutions.bin
    - save_solutions: save all solutions to best-solutions.bin
    - update_solution: update a single instance's solution if it improves on the current best
    - get_best_costs: quick lookup of {instance: cost} without loading full configurations

- solvers.py:
    - sat_solve_with_timeout: wrapper for solver.solve() with SIGALRM wall-clock timeout. Prevents SAT calls from hanging forever in C code.
    - build_occurrence_lists: build variable-to-clause index (hard_pos, hard_neg, soft_pos, soft_neg, soft_weights, soft_vars)
    - compute_sat_counts: compute per-clause satisfaction counts for an assignment
    - flip_variable: flip a variable and update all sat counts in place
    - compute_flip_delta: compute soft cost change from flipping a variable (without flipping)
    - flip_preserves_hard: check if flipping a variable would violate any hard clause
    - sat_init: find initial feasible assignment using pysat (supports solver_name='cd19' for CaDiCaL or 'g4' for glucose4)
    - greedy_sat: greedy SAT with selector variables for few-soft-clause instances (supports solver_name parameter)
    - tabu_search: tabu search on soft cost preserving hard feasibility, with configurable candidate variables
    - walksat_hard: WalkSAT to fix hard clause violations in an assignment
    - walksat_soft: WalkSAT-based soft clause optimizer for instances with many hard + soft clauses (O(clause_length) per step)
    - multi_init: run multiple SAT solvers with random assumptions to find diverse feasible solutions. Best for breaking out of single-solver local optima.
    - randomized_greedy: greedy SAT with random clause orderings. Dramatically better than weight-sorted for some instances. GAME-CHANGER for causal_n7 (optimal), timetabling.
    - simulated_annealing: SA on soft cost preserving hard feasibility. Exponential temperature schedule. Can escape local optima that tabu cannot.
    - assignment_to_lits: convert bytearray assignment to signed literal list

- core_guided.py:
    - core_guided_solve: naive core-guided solver — excludes all core literals. Fast but suboptimal.
    - core_guided_budget: core-guided with conflict budget — when SAT call exceeds budget, drops lightest assumption. Handles instances where regular core-guided hangs (synplicate). GAME-CHANGER.
    - wpm1_solve: WPM1-style core-guided solver with proper relaxation variables and at-most-one constraints.

- clause_weight_ls.py:
    - clause_weight_local_search: SATLike-inspired clause-weighting local search. Dynamically adjusts clause weights to escape local optima. Best for instances where tabu search gets stuck.
