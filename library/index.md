- tlsf_parser.py:
    - parse_tlsf: parse a TLSF file via syfco into LTL formula, inputs, outputs, semantics, status, ref_size
    - get_instance_stats: lightweight extraction of n_inputs, n_outputs, status, ref_size

- automata.py:
    - ltl_to_automaton: convert LTL formula to automaton (TGBA/BA/monitor) via ltl2tgba, returns HOA text
    - parse_hoa: parse HOA format into Python dict (states, edges, acceptance, APs)
    - automaton_to_parity: convert automaton to parity acceptance via autfilt
    - negate_formula: negate LTL formula (for unrealizability checking)
    - simplify_formula: simplify LTL formula via Spot's ltlfilt
    - automaton_stats: get state/edge/acceptance-set counts from HOA text

- games.py:
    - build_parity_game: construct 2-player parity game from parity automaton + I/O partition
    - zielonka_solve: Zielonka's recursive algorithm for parity games, returns winning regions
    - extract_strategy: extract memoryless strategy from winning region
    - strategy_to_mealy: convert strategy to Mealy machine representation

- circuits.py:
    - mealy_to_aiger: encode Mealy machine as AIGER circuit (aag format)
    - parse_aiger: parse aag format into Python structure
    - aiger_stats: extract AND gate count, latches, inputs, outputs from AIGER
    - validate_circuit: verify AIGER circuit against TLSF spec via ltlsynt
    - ltlsynt_solve: run ltlsynt on TLSF file as baseline (returns realizable/aiger/time)

- bounded_synth.py:
    - bounded_synth: encode "exists k-state controller?" as SAT via PySAT, solve
    - iterative_bounded_synth: try k=1,2,4,8... until realizable or timeout

- solutions.py:
    - load_solutions: load all best solutions from best-solutions.json
    - save_solutions: save solutions index to JSON
    - update_solution: update an instance's solution if it improves (new status or fewer AND gates)
    - mark_unrealizable: record that an instance is unrealizable
    - get_best_results: quick lookup of {instance: {status, and_gates}}

- synth.py:
    - parse_tlsf_quick: fast TLSF parsing via syfco → formula, inputs, outputs
    - solve_instance: full synthesis pipeline using Spot primitives (ltl_to_game → solve_game → mealy → AIGER)
    - verify_aiger: verify AIGER circuit against TLSF spec via ltlsynt --verify

- batch_solve.py:
    - load_reference: load reference.csv metadata
    - batch_solve: parallel multi-instance solver using ProcessPoolExecutor
    - CLI: --timeout, --workers, --family, --status-filter, --max-signals, --instances
