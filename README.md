```
    _                    _   ____    _  _____
   / \   __ _  ___ _ __ | |_/ ___|  / \|_   _|
  / _ \ / _` |/ _ \ '_ \| __\___ \ / _ \ | |
 / ___ \ (_| |  __/ | | | |_ ___) / ___ \| |
/_/   \_\__, |\___|_| |_|\__|____/_/   \_\_|
        |___/
```

An autonomous AI agent that teaches itself to become the world's top expert on MaxSAT. Given 229 weighted MaxSAT instances from the [2024 MaxSAT Evaluation](https://maxsat-evaluations.github.io/2024/) (main anytime weighted track), it discovers solving strategies, builds a library of tools, and grinds toward optimal solutions. No human guidance.

## Results so far (running around 15 hour)

| Metric | Count |
|--------|-------|
| Instances solved | **220 / 229** |
| Optimal (matching competition best) | **25** |
| **Better than competition** | **4** |
| Novel solve (no known solution existed) | **1** |
| Within 1.1x of reference | 95 |
| Within 1.5x | 151 |
| Within 2x | 189 |
| Unsolved | 9 |

### Beat the 2024 MaxSAT Competition

| Instance | Our cost | Competition best | Improvement |
|----------|----------|-----------------|-------------|
| switchingactivity_74 | 10 | 16 | **37.5% better** |
| synplicate dag_run2_16_size_9 | 333 | 398 | **16.3% better** |
| switchingactivity_68 | 8 | 9 | **11.1% better** |
| BTBNSL hailfinder_10000 | 49,986,819,152 | 50,007,681,202 | **0.04% better** |

### Solved what nobody else could

| Instance | Our cost | Notes |
|----------|----------|-------|
| pseudoBoolean mod010 | 8,081 | No competitor found any solution (ref=-1) |

## Techniques discovered

The agent developed these approaches autonomously, discovering what works through experimentation:

| Technique | Best for | Key insight |
|-----------|----------|-------------|
| **Greedy SAT** with selector variables | Few soft clauses (<500) | Heaviest-first greedy with CaDiCaL assumptions |
| **Core-guided search** | Unit soft clauses | Iterative UNSAT core relaxation. comp07.lp: 1778x → **optimal** |
| **WPM1 core-guided** | Weighted unit softs | Proper relaxation variables + at-most-one constraints |
| **Biased-SAT** | Breaking local optima | Random assumption subsets produce diverse solutions |
| **Clause-weighting LS** (SATLike) | Stuck at local optima | Dynamic weight adjustment escapes single-flip traps |
| **Tabu search** | No-hard / unit-soft instances | With SAT init + restarts. judgment-aggregation: 49x → 1.5x |
| **Multi-init** | Diverse starting points | Different solvers (CaDiCaL, glucose4, MiniCard) + random assumptions |
| **Alternating CWLS + WalkSAT** | Deep optimization | Alternating phases for continuous improvement. pa-1: 5445x → 612x |

## Hardest remaining

| Instance | Ratio | Why it's hard |
|----------|-------|---------------|
| relational-inference pa-1 | 612x | 2.5M vars, 1.1M soft clauses |
| polysite-bloat | 67x | 11.7M vars |
| haplotyping-13 | 13x | 215K vars, 18K softs |
| haplotyping-12 | 12x | 215K vars, 18K softs |
| twitter | 10x | 51K softs, 9.7M hard clauses |

9 instances remain unsolved — mostly >16M variables or no known reference solution.

## Library

All code the agent writes lives in `library/`:

| Module | Functions | Purpose |
|--------|-----------|---------|
| `solvers.py` | `greedy_sat`, `tabu_search`, `multi_init`, `sat_init`, `walksat_hard`, `walksat_soft`, `sat_solve_with_timeout` | Core solver building blocks |
| `core_guided.py` | `core_guided_solve`, `wpm1_solve` | UNSAT core-based optimization for unit soft clauses |
| `clause_weight_ls.py` | `clause_weight_local_search` | SATLike-inspired dynamic clause weighting |
| `solutions.py` | `load_solutions`, `update_solution`, `get_best_costs` | Compressed solution storage (1.7GB → 1.5MB) |
| `wcnf_parser.py` | `parse_wcnf`, `evaluate_cost`, `check_hard_clauses` | Single-pass streaming WCNF parser |

## How it works

1. An AI agent (e.g. Claude Code) reads `program.md` for instructions
2. It reads `expert.md` for accumulated knowledge from prior runs
3. It reads the library for available tools
4. It runs solvers on instances, discovers what works, updates everything
5. It commits and pushes to this repo so other agents can build on its findings

```
                              ┌─────────────────┐
                              │    GitHub Repo   │
                              │                  │
                              │  expert.md       │
                              │  library/        │
                              │  best-solutions  │
                              │  experiments.log │
                              └────────┬─────────┘
                           git pull/push │
                 ┌─────────────┬────────┴────────┬─────────────┐
                 │             │                 │             │
          ┌──────▼──────┐ ┌───▼────────┐ ┌──────▼──────┐     ...
          │   VM  1     │ │   VM  2    │ │   VM  3     │
          │             │ │            │ │             │
          │ ┌─────────┐ │ │ ┌────────┐ │ │ ┌─────────┐ │
          │ │ Agent 1 │ │ │ │Agent 3 │ │ │ │ Agent 5 │ │
          │ │ ┌─┬─┬─┐ │ │ │ │┌─┬─┬─┐│ │ │ │ ┌─┬─┬─┐ │ │
          │ │ │S│S│S│ │ │ │ ││S│S│S││ │ │ │ │S│S│S│ │ │
          │ │ └─┴─┴─┘ │ │ │ │└─┴─┴─┘│ │ │ │ └─┴─┴─┘ │ │
          │ ├─────────┤ │ │ ├────────┤ │ │ ├─────────┤ │
          │ │ Agent 2 │ │ │ │Agent 4 │ │ │ │ Agent 6 │ │
          │ │ ┌─┬─┬─┐ │ │ │ │┌─┬─┬─┐│ │ │ │ ┌─┬─┬─┐ │ │
          │ │ │S│S│S│ │ │ │ ││S│S│S││ │ │ │ │S│S│S│ │ │
          │ │ └─┴─┴─┘ │ │ │ │└─┴─┴─┘│ │ │ │ └─┴─┴─┘ │ │
          │ └─────────┘ │ │ └────────┘ │ │ └─────────┘ │
          └─────────────┘ └────────────┘ └─────────────┘

          S = solver process (python)
```

```bash
# Launch locally (benchmarks must already be in benchmarks/)
./run_local.sh

# Launch on EC2 (handles everything: installs deps, clones repo,
# downloads 4.3GB benchmarks from Helsinki, launches agent in tmux)
./run.sh ec2-user@<ip>
```

Requires a `.env` file with `CLAUDE_CODE_API_KEY` and `GITHUB_ACCESS_TOKEN`. The API key is auto-refreshed from your local Claude Code login on each deploy.

Multiple agents can work on the same repo simultaneously, communicating through git — each agent pulls the latest solutions and expert knowledge, builds on what others found, and pushes its own improvements. No coordination needed beyond `git pull` and `git push`.

## Known limitations

- **Low parallelism**: Claude Code rarely launches more than 6 parallel scripts, and often runs just 1-2 at a time, leaving most cores idle on large machines.
- **Tunnel vision**: The agent can fixate on grinding one instance for hours (e.g. pa-1 from 5445x to 612x over many rounds) while ignoring easier wins elsewhere.
- **Session length**: Despite "never stop" instructions, the agent tends to wrap up after a few hours, deciding it has reached a natural stopping point.

The agent maintains `expert.md` as a living knowledge base and improves the library as it learns.
