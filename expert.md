# LTL Reactive Synthesis Expert Knowledge

## Problem overview

**Reactive synthesis**: given an LTL specification over input and output signals, construct a controller (Mealy/Moore machine) that satisfies the spec for ALL possible input sequences, or determine that no such controller exists (unrealizable).

**Dual optimization goal**:
1. Determine realizability status for as many instances as possible (both realizable and unrealizable count)
2. For realizable instances, minimize AND gate count in the AIGER circuit encoding

## Available primitives

| Tool | Purpose | Notes |
|------|---------|-------|
| `syfco` | Parse TLSF files → LTL formula, inputs, outputs | Can't handle LTLf "strong next" operator |
| `ltlsynt` | Complete synthesis tool (most effective) | Has many algorithm/option combos |
| `spot` Python API | `ltl_to_game` → `solve_game` → AIGER | Available via `/opt/homebrew/bin/python3.14` |
| `ltl2tgba` / `autfilt` | LTL → automaton conversion | Lower-level building blocks |
| PySAT + CaDiCaL | SAT encoding for bounded synthesis | Implementation incomplete |

## Key algorithmic approaches

### 1. ltlsynt (most effective for breadth)
- `ltlsynt --tlsf=FILE --aiger --decompose=yes` is the single most effective command
- **Algorithm options**: `--algo=sd|ds|ps|lar|acd` — different algorithms solve different instances
  - `sd` (split-determinize): best for many Spectra/smart-home benchmarks
  - `ds` (determinize-split): complements sd, sometimes faster
  - `lar` (default): good general-purpose, handles large automata
  - `ps` (parity-split): rarely best but occasionally works where others fail
  - `acd`: alternative to lar, similar performance
- **Key flag**: `--decompose=yes` breaks spec into output-disjoint subproblems — CRITICAL for multi-output specs
- **Simplification**: `--simplify=bisim|bwoa|sat|bisim-sat|bwoa-sat` — default `bwoa` usually best
- **AIGER encoding**: `--aiger=both+ud+dc` tries multiple encodings and picks smallest

### 2. Spot Python API (good for unrealizability + small instances)
Pipeline: `spot.formula()` → `spot.ltl_to_game(f, outputs)` → `spot.solve_game(arena)` → `spot.solved_game_to_split_mealy()` → `spot.print_aiger()`

**Mealy optimization strategies** (try all, pick smallest):
- `solved_game_to_split_mealy` (default, fast)
- `simplify_mealy_here` with `minimize_lvl=2` or `3`
- `minimize_mealy` (unsplit, minimizes states)
- AIGER encodings: "isop", "ite", "both+dc", "both+ud+dc"

### 3. Re-optimization strategy (CRITICAL for circuit quality)
For instances already solved by spot_game, re-running with ltlsynt often produces **dramatically** smaller circuits:
- Coffee_235467da: 107,363 → 339 gates (99.7% reduction!)
- lazy_shades_problem: 51,554 → 3 gates
- lift_pb_5: 19,972 → 1,374 gates
- Many instances reduced from thousands to single-digit gates
The key insight: ltlsynt's `--decompose` + different algorithms explore very different solution spaces.

### 4. Family probing strategy (efficient for breadth)
Instead of trying all instances, test ONE instance per unsolved family first. If a family is tractable, batch-solve the rest. This identified 25+ tractable families in one pass.

## Benchmark landscape

- 1586 instances from SYNTCOMP 2025 LTL selection
- ~238 known realizable, ~111 known unrealizable, ~1237 unknown status
- Families include: amba, load_balancer, arbiter, collector, lift, ltl2dba, ltl2dpa, Spectra smart-home, etc.

## Instance family insights

### Instantly solvable (ltlsynt --decompose, <1s)
- **simple_arbiter_unreal1**: all 53 instances solved instantly. Decomposition is key.
- **prioritized_arbiter_unreal1/2**: most solved instantly with decompose
- **simple_arbiter_unreal2**: solved with decompose
- **gf-unreal family**: individual instances, each solved in <1s
- **F-G-contradiction**: solved with decompose
- **g-unreal**: most solved with decompose in <1s

### Solvable with moderate effort (1-30s)
- **ltl2dba_C2/E/Q/U1/theta**: realizable instances up to ~15 signals
- **lift, lift_gr1, lift_unary_enc**: realizable, moderate circuits
- **Spectra smart-home** (Lights, Coffee, Alarm, Shades, etc.): realizable, large circuits from spot but small from ltlsynt
- **amba_decomposed_arbiter/encode**: solvable with decompose
- **collector_v1/v3**: realizable, large game states

### Hard (>60s or intractable)
- **full_arbiter_unreal1**: X-nesting depth (u parameter) causes exponential game construction time. u≤18 works (~22s), u>20 intractable
- **round_robin_arbiter_unreal1**: similar to full_arbiter_unreal1, 3i/3o but deep nesting
- **numeric**: huge formulas (29K+ chars), no ltlsynt algorithm works in 30s
- **finding_nemo**: LTLf benchmarks using "strong next" operator, syfco can't parse
- **amba_decomposed_lock**: large signal counts (12-402), intractable
- **mux**: large signal counts (12-209)
- **shift**: up to 1000 signals, infeasible

## Approach selection guide

| Signals | Family type | Best approach |
|---------|-------------|---------------|
| ≤8 | Any unreal | ltlsynt --decompose (try sd, ds, lar) |
| ≤15 | Most families | ltlsynt --decompose + multiple algos |
| ≤15 | Arbiter unreal (high params) | spot game (slow but works if game builds in time) |
| 15-25 | Spectra/smart-home | ltlsynt-sd+decompose (produces smallest circuits) |
| 15-25 | AMBA decomposed | ltlsynt+decompose |
| >25 | Any | Likely intractable with current tools |

**For circuit quality**: Always re-optimize spot_game solutions with ltlsynt --algo=sd --decompose=yes --aiger=both+ud+dc

## Approaches that DON'T work

- **Spot game on high-parameter arbiters**: X^u nesting with u>20 causes game construction to exceed any reasonable timeout (exponential in u)
- **Bounded synthesis (current implementation)**: SAT encoding is incomplete, doesn't properly encode automaton transitions
- **ltlsynt without --decompose**: Dramatically slower on multi-output specs
- **Single algorithm**: No single ltlsynt algorithm dominates — sd, ds, lar each win on different instances
- **Python subprocess nesting**: Running python3.14 via subprocess from python3.14 is unreliable for background tasks (output buffering issues)
- **syfco on LTLf specs**: "strong next" operator not supported

### 5. Singleton/small family sweep (highest ROI)
Many benchmark families have only 1-3 instances. These are often trivially solvable but were missed because batch scripts focused on large families. A targeted sweep found 88 new solutions in one pass.

## Current status

**1112 solved / 1586 total** (477 realizable, 635 unrealizable) = 70.1%

**Remaining 474 instances** are genuinely hard — all timeout with ltlsynt (all 6 algorithms + decompose + formula simplification), spot game, lar.old, ps within 15-120s budgets.

**Hard remaining families**:
- full_arbiter_unreal1 (26): X-nesting depth causes exponential game construction
- round_robin_arbiter_unreal1 (25): similar to full_arbiter
- chomp (12): large formulas, solvable for small params (2x2, 3x2) but not larger
- amba_decomposed_arbiter/encode (11 each): larger instances timeout
- amba_gr/gr+ (11 each): never cracked, 22-66 signals
- numeric (9): 29K+ character formulas, intractable
- finding_nemo (7): LTLf with "strong next" operator, needs LTLf-specific synthesis

### 6. Quick probe strategy (discovered late — high impact)
Running ltlsynt with very short timeouts (5s) and `--bypass=yes` (default) can find instances that longer runs miss, because the bypass optimization avoids full game construction for trivially decomposable specs. This found 96 instances in one pass.

**Next priorities**:
1. Implement proper bounded synthesis (SAT-based) for small instances where automata-based approaches fail
2. Build custom approach for parametric arbiter_unreal families (exploit formula structure)
3. Handle LTLf instances (finding_nemo) — need `spot.ltlf_to_mtdfa_for_synthesis` or direct TLSF parsing
4. Run on EC2 with 5+ minute timeouts per instance for borderline cases (Alarm, AllLights, Morning families)
5. Explore ABC/yosys for post-synthesis circuit optimization
6. Try `spot.reduce_mealy` for circuit size reduction on existing solutions
