# MaxSAT Expert Knowledge

## Overall results summary

- **220/229 instances solved** (9 remaining)
- **5 better than competition reference** + 1 with no known reference (pseudoBoolean) + 1 matching optimal (causal_n7)
- **123 within 1.1x** of reference, **30 optimal** (matching reference exactly)
- **209 within 2x**, 10 still >2x
- **quantum-circuit qgan: OPTIMAL** via RC2 with CaDiCaL
- **SA from existing is a universal improver**: improved judgment-aggregation (1.47x→1.04x), railway-transport (1.64x→1.32x), drmx-cryptogen (1.08x→1.05x), and more
- **haplotyping-12: 3.78x→1.01x** via RC2 on heavy softs (w=581)
- **haplotyping-13: 12.6x→1.01x** via WPM1 on heavy softs (bimodal weight decomposition)
- **setcover: all 6 instances dramatically improved** via domain-specific greedy set cover: rail2536 2.12x→1.23x, rail4284 2.07x→1.22x, rail4872 1.89x→1.23x, rail507 1.72x→1.20x, rail582 1.75x→1.17x
- **ParametricRBAC domino 0.7_0: 1.82x→1.25x**, **domino 0.4_0: 1.56x→1.24x** via CGB on top-2 weight levels
- **comp09: 2.25x → 1.50x** via randomized greedy
- **polysite-bloat: 66x → 2.0x** via heavy-as-hard + greedy SAT
- **downcast-pmd: 2.08x→1.21x** via WPM1 on heavy softs
- **pa-1 reduced from 5445x to ~602x** via biased-sat + alternating CWLS/walksat

## Approach selection guide

The single most important factor is **number of soft clauses** (nsofts), not total variables or clauses.

### Solver selection: CaDiCaL vs glucose4
- **CaDiCaL (cd19)** is the default solver for everything. It solved instances in <0.3s where glucose4 was stuck for 10+ minutes.
- glucose4 ('g4') is only useful for very small instances or as a fallback.
- The `greedy_sat()` and `sat_init()` functions accept a `solver_name` parameter.
- **ALWAYS use `solver_name='cd19'`** unless you have a specific reason not to.

### No hard clauses (nhards=0)
- **Tabu search** with weighted polarity initialization: produces optimal solutions given enough time (250s).
- Key: polarity init, tabu tenure ~nvars/20.
- Achieved optimal on all 4 ramsey instances (55-153 vars).

### Few soft clauses (nsofts < 500) with hard clauses
- **Greedy SAT with selector variables** (CaDiCaL): The most powerful approach.
  - O(nsofts × SAT_time_per_call), perfect for few-soft instances
  - Some instances have slow per-call SAT (~seconds), so total time = nsofts × per-call time
  - Achieved **optimal** or **near-optimal** on: af-synthesis (all 15), preference_planning, synplicate, CSG, lisbon-wedding (most), planning, protein_ins, BTBNSL

### Unit soft clauses with many hard clauses (judgment-aggregation, haplotyping)
- **Tabu search from existing best** is the most effective approach.
- judgment-aggregation: all softs unit, all hards 3-literal. ~6K vars, ~1.2M hards.
  - Starting from fresh SAT init: 20-49x → 1.5-1.8x
  - Starting from existing best + tabu: further improved to **1.22-1.48x**
  - Key: load existing solution with `load_solutions()`, seed tabu search from it
  - Key parameters: restarts=5, perturb_prob=0.05, timeout=240

### Many soft clauses (nsofts > 500) with hard clauses
- **SAT baseline** gives decent results for most families
- **Tabu search** can improve but is slow per step for large occurrence lists (>1M hard clauses)
- **Greedy SAT** with CaDiCaL works for up to ~6000 soft clauses within 300s budget

### Very large instances (>1M vars)
- CaDiCaL handles many instances that glucose4 cannot (up to ~12M vars in some cases)
- 9 instances still unsolved — mostly >16M vars or no known reference

## Instance family insights

| Family | Solved | Optimal | Best quality | Notes |
|--------|--------|---------|-------------|-------|
| ramsey (4) | 4/4 | 4 | all optimal | Tabu search |
| synplicate (25) | 25/25 | 5 | 1.0-4.7x | CaDiCaL greedy + multi-init |
| switchingactivity (9) | 9/9 | 3 | 0.62-3.0x | CaDiCaL greedy, 2 beat reference |
| af-synthesis (15) | 15/15 | 0 | 1.06-1.23x | CaDiCaL greedy, all solved |
| protein_ins (7) | 7/7 | 0 | 1.006-1.013x | Near-perfect |
| BTBNSL (14) | 14/14 | 0 | 1.00-1.5x | 1 beats reference (hailfinder_10000) |
| decision-tree (15) | 15/15 | 0 | 1.36-3.1x | CaDiCaL greedy + multi-init |
| judgment-aggregation (13) | 13/13 | 0 | 1.16-1.48x | Tabu from existing best |
| ParametricRBAC (15) | 15/15 | 0 | 1.0-2.4x | Core-guided + multi-init |
| lisbon-wedding (13) | 13/13 | 1 | 1.0-2.0x | CaDiCaL greedy+SAT baseline |
| correlation-clustering (12) | 12/12 | 0 | 1.16-4.5x | Multi-init dramatically improved |
| abstraction-refinement (11) | 11/11 | 0 | 1.02-137x | polysite-bloat solved via CaDiCaL |
| timetabling (8) | 8/8 | 2 | 1.0-11.7x | comp07.lp now optimal via core-guided |
| setcover (6) | 6/6 | 0 | 1.1-1.2x | Domain-specific greedy set cover |
| planning (3) | 3/3 | 1 | 1.0-1.29x | |
| max-realizability (4) | 4/4 | 0 | 1.10-1.29x | Multi-init improved |
| CSG (2) | 2/2 | 2 | both optimal | |
| railway-transport (4) | 4/4 | 0 | 1.003-1.64x | CaDiCaL greedy |
| causal-discovery (5) | 5/5 | 1 | 1.0-2.5x | n7 solved via greedy SAT |

## Key technical insights
- **CaDiCaL (cd19) >> glucose4** for everything. Always use CaDiCaL.
- **Greedy SAT with selector variables**: O(nsofts × SAT_time_per_call), the workhorse
- **Tabu search** with SAT init: transformative for unit soft clauses (judgment-aggregation: 20-49x → 1.5-1.8x)
- **Core-guided search** is transformative for unit soft clause instances (comp07.lp 1778x→optimal)
- **SAT solver calls can hang forever** — pysat's `solver.solve()` enters C code and won't return to Python if the problem is too hard. Always use `sat_solve_with_timeout()` from `library/solvers.py` which uses SIGALRM to interrupt hung calls. Without this, core-guided on synplicate hangs indefinitely.
- **RC2 is unreliable** — times out even on 58-var instances. Don't use.
- **SAT baseline** is often surprisingly good (abstraction-refinement, BTBNSL, protein_ins, correlation-clustering)
- Some instances with slow per-call SAT only get partial greedy improvement (lisbon-wedding 9-17, 8-17, 7-19 got baselines only)

## Key packages
- **python-sat (pysat)**: Solver class with CaDiCaL (cd19) and glucose4 (g4)
- **numpy**: for custom search implementations

## Notable results

### Better than 2024 MaxSAT competition reference
- **switchingactivity_74**: cost=10, ref=16 (37.5% better)
- **switchingactivity_68**: cost=8, ref=9 (11% better)
- **BTBNSL hailfinder_10000**: cost=49,986,819,152, ref=50,007,681,202 (0.04% better)

### Solved with no known reference (ref=-1 in competition)
- **pseudoBoolean**: cost=8081 (no competitor found a solution)

## Remaining unsolved (9)
1. MinimumWeightDominatingSetProblem (4 of 10): delaunay_n24, hugebubbles, inf-road-usa, rgg_n_2_24 — too large (>16M vars)
2. MinimumWeightDominatingSetProblem socfb-uci-uni: 3.1GB, ref=-1 (no known solution)
3. lisbon-wedding-1-19 and lisbon-wedding-3-18: ref=-1 (no known solution)
4. relational-inference pa-2 and pa-3: 18M+ vars

### Multi-init: different SAT solver seeds produce different solutions
- **Key discovery**: running multiple SAT solvers (cd19, g4, cd15, mc) with random assumptions produces wildly different assignments with different soft costs
- Extremely effective for breaking out of SAT baseline local optima
- Example: correlation-clustering Protein1_N270 went from 10.2x to 2.68x just from a different solver seed
- Example: correlation-clustering Protein1_N250 went from 9.4x to 1.86x
- Example: decision-tree primary-tumor went from 7.3x to 2.8x
- Runs 50-500 trials in 15-30s per instance
- Does NOT help for judgment-aggregation (all SAT baselines are terrible for these)


### Bimodal weight decomposition (GAME-CHANGER)
- **Key discovery**: many instances have bimodal weight distributions (e.g., weights {1, 581} or {1, 4230})
- Running WPM1 or core-guided specifically on the HEAVY soft clauses finds dramatically better solutions
- The light softs are essentially "free" — the solver satisfies most of them as a side effect
- **Why it works**: with all softs combined, the solver loses precision on heavy clauses because it trades off too many of them against light ones. Focusing on heavy softs alone finds tighter relaxations.
- **Haplotyping-13**: 511K → 41K (12.6x → 1.01x, near-optimal!) — weights {1: 580, 581: 18400}
- **Haplotyping-12**: 668K → 207K (12.2x → 3.78x)
- **polysite-bloat**: 2397 → 86 (66x → 2.4x) — weights {1: 4948, 4230: 1038}
- **downcast-pmd**: 8791 → 5115 (2.08x → 1.21x) — weights {1: 4605, 4186: 420}
- **When to use**: any instance with ≥2 distinct weights where max_weight > 5 × min_weight
- **How**: separate heavy (w > min_w * 2) from light, run WPM1 on heavy, evaluate full cost
- If WPM1 times out, use core_guided_budget on heavy softs as fallback

### Core-guided search for unit soft clauses
- **Key discovery**: many of the worst-ratio instances have unit (single-literal) soft clauses
- Core-guided approach: use SAT solver assumptions to iteratively find and relax unsatisfiable cores
- **Game-changer results**:
  - timetabling comp07.lp: 1778x → **optimal** (cost 3, ref 3)
  - ParametricRBAC domino: 2.6-3.2x → 1.56-2.44x across all instances
  - polysite-bloat: unsolved → solved
- Works because unit soft clauses map directly to assumption literals
- Should be tried on ALL instances with unit soft clauses before other approaches

### Heavy-as-hard + greedy SAT (for instances with 2 distinct weight classes)
- **Key discovery**: instances with 2 distinct soft clause weights benefit hugely from treating the heavier class as hard constraints, then greedily satisfying the lighter class
- Process: (1) add all hard clauses + heavy soft clauses as hard, (2) add selector variables for light soft clauses, (3) greedily add selectors as assumptions
- **Dramatically better than core-guided alone** because it guarantees all heavy clauses satisfied
- **Game-changer results**:
  - polysite-bloat: 2397 → 72 (66.6x → 2.0x). Has 1038 weight-4230 + 4948 weight-1 softs. Greedy gets through ~130 iterations per run (each SAT call ~1.7s)
  - timetabling test4: 506 → 438 (3.78x → 3.27x). Has 193 weight-5 (unit) + 1375 weight-2 (non-unit) softs
- **Can be continued incrementally**: load existing solution, find which light softs are already satisfied, only try unsatisfied ones
- Works best when: (a) few distinct weight classes, (b) SAT calls are fast enough for greedy iteration
- Does NOT help when: all soft clauses have the same weight (no weight-class separation)

### Biased-SAT with random assumption subsets
- **Key discovery**: for instances where full assumption sets hang the solver, random subsets work excellently
- Creates fresh SAT solver per trial, picks random subset of soft clause literals as assumptions
- The SAT solver naturally satisfies many soft clauses beyond what's assumed, often finding near-optimal solutions
- **Game-changer for synplicate family**: where core-guided and RC2 both time out, biased-sat with n=3-40 random assumptions produces rapid improvements
- Example results:
  - synplicate dag_run2_12: 959→598 (2.32x→1.45x)
  - synplicate size10 arity3/f3: 654→507 (3.59x→2.79x)
  - causal_Water: 15.75M→8.31M (8.35x→4.40x)
  - relational-inference pa-1: 4.47M→1.15M (5445x→1404x)
- Does NOT help for instances with too-expensive SAT calls (>5s per solve, e.g. twitter with 9.7M hard clauses)
- Sweet spot: 50-200 unit softs, <1M hard clauses, <500K vars

### Alternating CWLS + WalkSAT-soft
- **Key discovery**: alternating between CWLS and walksat-soft from an existing solution yields continuous improvement
- CWLS escapes local optima via dynamic weighting; walksat-soft then explores from the new position
- Most effective on instances with many soft clauses (>10K)
- **Game-changer for pa-1**: 4.47M → 688K (5445x → 839x) over ~8 rounds
- Each round typically reduces cost by 3-8%
- Eventually converges, but many rounds are worthwhile

### Clause-weighting local search (SATLike-inspired)
- Dynamically increase weights of unsatisfied soft clauses to escape local optima
- Periodically smooth weights back to prevent explosion
- Effective where tabu search gets stuck at single-flip local optima
- Effective for haplotyping: improved haplotyping-13 from 559K→512K, haplotyping-12 from 963K→668K

### Naive core-guided for correlation-clustering
- Core-guided (exclude all core literals) works well on correlation-clustering Ionosphere
  - N280: 32.3M→14.2M (4.50x→1.98x)
  - N300: 34.3M→16.5M (4.25x→2.04x)
- Also improved Vowel N700: 144.9M→119.9M (2.00x→1.66x)
- Works less well on Protein variants (same or worse cost)

### Split-heavy approach for bimodal weight instances
- **Key discovery**: when soft clauses have bimodal weight distribution (few heavy + many light), treat heavy clauses as hard constraints and optimize only light clauses
- Works when: enforcing all heavy as hard is SAT (otherwise need partial enforcement or skip)
- **Game-changer results**:
  - polysite-bloat: 2397→86 (66x→2.4x). Add 1038 w=4230 clauses as hard, greedy SAT on 4948 w=1 clauses
  - timetabling_test4: 629→448. Add w=5 as hard, greedy on w=2
- Does NOT work when heavy clauses conflict (e.g. haplotyping: adding all 18400 w=581 clauses → UNSAT)

### Randomized greedy SAT ordering
- **Key discovery**: standard greedy SAT sorts by weight descending, but random orderings can find dramatically better solutions
- The weight-descending order is a greedy heuristic that can get stuck in suboptimal local optima
- Random orderings explore different corners of the solution space
- **Game-changer results**:
  - causal_n7: 94.9B→37.5B (2.53x→**optimal**, matching reference)
  - Found optimal in just 43 trials of random ordering
- Most effective for instances with <5000 soft clauses where each greedy iteration is fast
- Run 50-100 random orderings to find good solutions

### Simulated annealing as universal improver (GAME-CHANGER)
- **Key discovery**: SA from existing solution is the most broadly effective improvement technique
- Works on ANY instance with many soft clauses (>500) where the existing solution isn't already optimal
- Exponential temperature schedule: t_start=0.3, t_end=0.000001, with 20-60s per instance
- **Game-changer results**:
  - judgment-aggregation: 1.47x→1.04x (multiple instances to near-optimal ~1.02-1.05x)
  - railway-transport bf2030fvslack: 1.36x→1.08x, r11: 1.64x→1.32x
  - drmx-cryptogen: 1.08x→1.05x (all 5 instances)
- SA accepts worse moves probabilistically → escapes local optima that tabu/CWLS cannot
- Each additional SA run has diminishing returns but still finds improvements (run multiple rounds)
- Does NOT work well on instances with few soft clauses (<500) or very expensive per-flip operations

## Current bottleneck: single-flip local optima
Most solved instances are at single-flip local optima — no single variable flip can improve soft cost without breaking hard constraints. Further improvements require:
1. **Multi-variable moves** (2-opt, 3-opt swaps)
2. **C/Cython tabu** for faster per-step execution on large instances
3. **Domain-specific decomposition** (especially for ParametricRBAC, correlation-clustering)
4. **Longer running times** for tabu search on instances with slow per-step operations

## Approaches that DON'T work
- **WalkSAT soft on correlation-clustering**: SAT baseline is at hard local optimum, no single flip improves
- **CaDiCaL baseline for haplotyping**: glucose4 baseline is BETTER for haplotyping (1.2M vs 6.6M)
- **Tabu search on large occurrence lists**: too slow per step with >1M hard clauses (ParametricRBAC domino, timetabling)
- **RC2 on synplicate/timetabling**: times out even with 120s budget — formula too complex
- **Core-guided with full assumptions on synplicate**: SAT solver hangs — use biased-sat instead
- **WPM1 on >40K assumptions**: returns None (too many cores to process). Failed on twitter (45K heavy softs) and haplotyping-12 (18.4K heavy softs, though RC2 worked)
- **Multi-init on setcover**: gives 1000-3000x ratios because random SAT assignments select way too many sets. Use domain-specific greedy instead.
- **Biased-sat on twitter (51K softs, 9.7M hards)**: each SAT call too expensive (~5s), no improvement
- **Greedy SAT with >15K vars per soft call**: each SAT call takes >10s, so greedy loop times out
- **walksat_soft and CWLS on twitter**: both fail to escape the existing local optimum (138K cost vs 14K ref)
- **SA/tabu from existing on decision-tree**: stuck at single-flip local optima with expensive per-step operations
- **Nested signal.alarm() calls**: inner finally block clears outer alarm, causing processes to hang indefinitely. Use subprocess timeout instead.

## Next steps for improvement
1. **pa-1 (602x)**: 2.5M vars, 1.9M hards, 1.1M softs — too large for SAT-based approaches. Continue CWLS+walksat iterations.
2. **twitter (9.65x)**: 45K heavy unit softs (w=10) + 6K light (w=1). WPM1/CGB/walksat/CWLS all fail. Need fundamentally different approach.
3. **causal_Water (4.40x)**: 869K vars, biased-sat helps slightly but not enough. Need more aggressive multi-init or decomposition.
4. **timetabling test4 (3.31x)**: RC2 (cd19, g4) times out, CWLS/tabu from existing don't improve. Bimodal {2, 5} with 69K vars.
5. **decision-tree (2.5x)**: 3 instances, 268-765 softs, 2.5M hards. RC2 times out, SA doesn't improve. Need faster SAT per call.
6. **ParametricRBAC domino (2.0-2.4x)**: 3 instances, 34K unit softs. CGB-heavy only helps when heavy/light ratio is >100x. walksat_soft doesn't improve. Need different decomposition.
7. **Solve remaining 9**: 4 MinWeightDomSet too large, 2 lisbon-wedding extremely hard SAT, 1 MinWeightDomSet no ref, 2 relational-inference 18M+ vars

### RC2 (pysat MaxSAT solver) - REVIVED
- **Previously dismissed as unreliable**, but with CaDiCaL backend (solver='cd19') and proper timeout, RC2 finds OPTIMAL solutions
- **comp06: 50→27 (OPTIMAL)**, **quantum-circuit: 48→27 (OPTIMAL)** in <45s each
- **haplotyping-12: 206K→55K (3.78x→1.01x)** — RC2 on heavy softs (w=581) where WPM1 failed
- Key: use subprocess with timeout (NOT nested signal.alarm, which has bug where inner finally clears outer alarm)
- Works best on instances with <200K vars, <1M hards, <5K softs
- **Also works on SUBSETS of soft clauses**: when bimodal, run RC2 on just the heavy softs
- Does NOT work on timetabling test4/comp02 (too large), decision-tree (2.5M hards too slow)
- Always try RC2 first on any instance within its size limits

### Domain-specific greedy set cover (GAME-CHANGER for setcover family)
- **Key discovery**: setcover instances have special structure (few coverage constraints, many set variables)
- Standard MaxSAT solvers (SAT-based, multi-init) are terrible for these: they select random sets, getting 1000-3000x ratios
- **Greedy set cover**: iteratively pick set with best (uncovered_elements / weight) ratio
  - Multiple randomized trials with noise on ratio scoring to explore different solutions
  - Local optimization: remove redundant sets (sets whose covered elements are all covered by other selected sets)
- **Game-changer results**: rail2536: 2.12x→1.23x, rail4284: 2.07x→1.22x, rail4872: 1.89x→1.23x, rail507: 1.72x→1.20x, rail582: 1.75x→1.17x
- Structure detection: nhards << nsofts, soft clauses are unit negative literals (-x), hard clauses are positive disjunctions
- Could potentially be improved further with swap neighborhoods or LP relaxation

### CGB on top-2 weight levels (for ParametricRBAC domino)
- **Key discovery**: when instances have 4+ weight levels, running CGB on just the top-2 weight classes can dramatically improve solutions
- Works when: (a) top-2 weight classes have few clauses (< 200), (b) heavy-to-light weight ratio is large (>100x)
- **Results**: domino_0.7_0: 1.82x→1.25x (weights 7000/3590 vs 39/9), domino_0.4_0: 1.56x→1.24x
- Does NOT work when heavy-to-light ratio is small (domino_0.1_1: weights 1045/526 vs 28/6, got 7x worse)
