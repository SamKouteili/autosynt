GOAL:

The goal is twofold:

1. **Become the world's best MaxSAT expert** — accumulate deep knowledge in `expert.md` and build powerful tools in `library/`. This knowledge compounds: what you learn on one instance should make you better at all future instances.
2. **Find the best possible configuration for each benchmark instance** — by any means necessary. There is no single "solver" you are building. You might chain multiple approaches, use one solver's output to seed another, manually reason about variable assignments, exploit instance structure, whatever works. The configuration is what matters, not the method.

ENVIRONMENT:

- expert.md: the core knowledge base. Contains everything you know about solving MaxSAT — strategies, tricks, rules of thumb, instance family insights, solver comparisons, failure modes, and so on. This is the most important file in the project. It should be a live reflection of your current understanding — not a polished report you write at the end. Update it after every significant experiment or discovery. Write down what you tried, what happened, and what it suggests, even if you're not sure yet. Partial insights are valuable. If you've run 3+ experiments without updating expert.md, you're falling behind. And updates are not append-only: as your understanding evolves, restructure, revise, or remove things that turned out to be wrong. The document should always reflect your current best view, not a chronological log.
- library/: your codebase. All code lives here — solvers, analysis tools, utilities, everything. `library/index.md` has a full overview. Write code directly in the library as reusable, documented functions. When you run experiments, write inline scripts that import from the library. Every technique described in `expert.md` should have a corresponding implementation here. Like `expert.md`, the library is a living thing — update, improve, or remove code as your understanding evolves.
- experiments.log: append-only log of every experiment you run. Format per line:
  ```
  [YYYY-MM-DD HH:MM:SS] instance: <name> | approach: <short description> | cost: <number or FAIL> | time: <seconds> | notes: <what was learned>
  ```
- best-solutions.bin: tracks the best configuration found for each instance in compressed binary format. Use `library/solutions.py` to read and write this file — never edit it directly. Key functions:
  - `load_solutions()` → dict of all solutions
  - `update_solution(instance, cost, configuration, method)` → True if new best
  - `get_best_costs()` → quick lookup of {instance: cost} without loading configurations
  Configurations are lists of signed literals (positive = true, negative = false), following DIMACS convention. `cost` is the sum of weights of unsatisfied soft clauses. Keep it up to date whenever you find a better solution.
- benchmarks/: benchmark instances. Nothing in this directory should be modified.
    - max-sat-2024/:
        - instructions.txt: **read this first.** Contains the problem definition, WCNF format spec, and cost definition.
        - best-costs.csv: best known costs at the time of the 2024 MaxSAT competition. Better costs may or may not exist. Format: `instance,best_cost` (-1 means no known solution). Read this to know what you're shooting for.
        - mse24-anytime-weighted/: directory with all 229 instances.

RULES:

- Max runtime for any single script is 300 seconds — this means the entire script, not each function call within it. Do not write scripts that loop over many instances sequentially. Instead, write scripts that solve, research or analyze one instance (or a small batch) and run multiple scripts in parallel. Put appropriate time guards so this is never exceeded.
- If something gets terminated because of the timeout, make sure to at least have logs to learn from.
- Maximize parallelism. Run as many scripts in parallel as the server can handle — monitor CPU usage and keep idle resources near zero. If cores are sitting idle, launch more work.
- Never stop. Only the user can stop you. Nobody else.
- You can use the browser, read papers, or any other tool at your disposal.
- All code runs locally, in Python, CPU only.
- You can install any Python packages freely.
- Make sure any code you run is fast to get as many operations in as possible before the time limit.
- Only work on instances provided in the benchmarks/ directory.
- There are multiple agents working on this repo simultaneously. Pull before starting work and commit+push frequently — every improvement to `best-solutions.bin`, every update to `expert.md`, every new or changed file in `library/`, every batch of `experiments.log` entries. Other agents depend on your commits to avoid duplicating work and to build on your findings. If you haven't committed in 10 minutes, you're falling behind.

TIPS:

- Start by understanding the benchmark landscape — instance sizes, families, difficulty ranges. Not all instances are equal; some have millions of variables, others have dozens.
- Establish baselines early. A simple solver run across a few instances tells you where the low-hanging fruit is.
- You don't need to work through instances in order. Jump to where you think you can make the most progress.
- After significant progress or learning, update `expert.md` and commit. Knowledge that isn't written down is knowledge lost.
- If you're not making progress on an instance, move on to a different one or a different approach. Revisit later with fresh knowledge.
