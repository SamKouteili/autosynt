GOAL:

The goal is twofold:

1. **Become the world's best LTL reactive synthesis expert** — accumulate deep knowledge in `expert.md` and build powerful tools in `library/`. This knowledge compounds: what you learn on one instance should make you better at all future instances.
2. **Solve as many SYNTCOMP instances as possible and minimize circuit size** — for each benchmark instance, determine if it is realizable or unrealizable, and for realizable instances, produce a controller circuit with as few AND gates as possible. There is no single "solver" you are building. You might chain multiple approaches, use one tool's output to seed another, exploit spec structure, whatever works. The result is what matters, not the method.

ENVIRONMENT:

- expert.md: the core knowledge base. Contains everything you know about LTL synthesis — strategies, tricks, rules of thumb, instance family insights, technique comparisons, failure modes, and so on. This is the most important file in the project. It should be a live reflection of your current understanding — not a polished report you write at the end. Update it after every significant experiment or discovery. Write down what you tried, what happened, and what it suggests, even if you're not sure yet. Partial insights are valuable. If you've run 3+ experiments without updating expert.md, you're falling behind. And updates are not append-only: as your understanding evolves, restructure, revise, or remove things that turned out to be wrong. The document should always reflect your current best view, not a chronological log.
- library/: your codebase. All code lives here — synthesis tools, analysis utilities, everything. `library/index.md` has a full overview. Write code directly in the library as reusable, documented functions. When you run experiments, write inline scripts that import from the library. Every technique described in `expert.md` should have a corresponding implementation here. Like `expert.md`, the library is a living thing — update, improve, or remove code as your understanding evolves.
- experiments.log: append-only log of every experiment you run. Format per line:
  ```
  [YYYY-MM-DD HH:MM:SS] instance: <name> | approach: <short description> | status: realizable/unrealizable/timeout | and_gates: <N or N/A> | time: <seconds> | notes: <what was learned>
  ```
- best-solutions.json: tracks the best result found for each instance. Use `library/solutions.py` to read and write — never edit directly. Key functions:
  - `load_solutions()` → dict of all solutions
  - `update_solution(instance, status, aiger_text, method)` → True if new best
  - `mark_unrealizable(instance, method)` → record unrealizability
  - `get_best_results()` → quick lookup of {instance: {status, and_gates}}
  Individual AIGER circuit files are stored in `solutions/`.
- benchmarks/: benchmark instances. Nothing in this directory should be modified.
    - syntcomp-2025/:
        - reference.csv: instance metadata — status (realizable/unrealizable/unknown), ref_size (AND gates of reference solution), n_inputs, n_outputs, semantics, family. Read this to know what you're shooting for.
        - instances/: directory with all 1586 TLSF instances from the SYNTCOMP 2025 LTL selection.

RULES:

- Max runtime for any single script is 300 seconds — this means the entire script, not each function call within it. Do not write scripts that loop over many instances sequentially. Instead, write scripts that solve, research or analyze one instance (or a small batch) and run multiple scripts in parallel. Put appropriate time guards so this is never exceeded.
- If something gets terminated because of the timeout, make sure to at least have logs to learn from.
- Use parallelism carefully. When running batch solves, limit to 4 workers max (`ProcessPoolExecutor(max_workers=4)`). Spot and SAT solvers use significant memory per process — 45 parallel Python processes will eat all RAM and crash the machine. Monitor memory, not just CPU.
- Never stop. Only the user can stop you. Nobody else.
- You can use the browser, read papers, or any other tool at your disposal.
- All code runs locally, in Python, CPU only.
- You can install any Python packages freely.
- **CRITICAL**: Your value comes from engineering better synthesis approaches, not from wrapping existing tools. You may use ltlsynt as ONE approach among many, but you should also build your own approaches from lower-level primitives — `ltl2tgba`/`autfilt` for automaton construction, the `spot` Python library, PySAT for SAT-based bounded synthesis, custom game solvers, circuit minimization, etc. If all you're doing is calling `ltlsynt --tlsf` on every instance, you're not learning anything and not adding value. The goal is to develop techniques that work where ltlsynt fails, or produce smaller circuits where it succeeds.
- Make sure any code you run is fast to get as many operations in as possible before the time limit.
- Only work on instances provided in the benchmarks/ directory.
- There are multiple agents working on this repo simultaneously. Pull before starting work and commit+push frequently — every improvement to `best-solutions.json`, every update to `expert.md`, every new or changed file in `library/`, every batch of `experiments.log` entries. Other agents depend on your commits to avoid duplicating work and to build on your findings. If you haven't committed in 10 minutes, you're falling behind.

TIPS:

- Start by understanding the benchmark landscape — instance sizes, families, difficulty ranges. Read reference.csv. Not all instances are equal; some have dozens of signals, others have 2.
- Start with a few small instances to understand the problem. Then build multiple approaches — use ltlsynt as one baseline, but also build your own pipeline (automaton → game → strategy → AIGER), try SAT-based bounded synthesis via PySAT, explore the Spot Python library, etc. The more diverse your approaches, the more instances you can solve and the better circuits you can produce.
- Identify structural subsets: GR(1) specs can be solved in polynomial time, safety specs have simpler game structures, small specs (few inputs/outputs) are amenable to bounded synthesis.
- You don't need to work through instances in order. Jump to where you think you can make the most progress.
- After significant progress or learning, update `expert.md` and commit. Knowledge that isn't written down is knowledge lost.
- If you're not making progress on an instance, move on to a different one or a different approach. Revisit later with fresh knowledge.
