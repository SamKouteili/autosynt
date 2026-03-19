#!/usr/bin/env python3.14
"""Re-optimize existing realizable solutions to reduce AND gate counts.
Uses Spot's mealy simplification + multiple AIGER encodings."""

import csv
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
INSTANCES_DIR = ROOT / "benchmarks" / "syntcomp-2025" / "instances"
REFERENCE_CSV = ROOT / "benchmarks" / "syntcomp-2025" / "reference.csv"
EXPERIMENTS_LOG = ROOT / "experiments.log"

sys.path.insert(0, str(ROOT))

import spot


def try_aiger(mealy, enc):
    """Try encoding mealy as AIGER with given encoding. Returns (text, gates) or (None, None)."""
    try:
        oss = spot.ostringstream()
        spot.print_aiger(oss, mealy, enc)
        text = oss.str()
        header = text.strip().split('\n')[0].split()
        gates = int(header[5])
        return text, gates
    except Exception:
        return None, None


def resynthesize(tlsf_path, current_gates, timeout=120):
    """Re-synthesize instance trying to beat current_gates."""
    start = time.time()
    tlsf_path = str(tlsf_path)

    try:
        formula = subprocess.run(
            ["syfco", "-f", "ltlxba", "-m", "fully", tlsf_path],
            capture_output=True, text=True, timeout=30
        ).stdout.strip()
        outs_str = subprocess.run(
            ["syfco", "-outs", tlsf_path],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
        outputs = [s.strip() for s in outs_str.split(",") if s.strip()]

        if not formula:
            return None

        f = spot.formula(formula)
        remaining = timeout - (time.time() - start)
        if remaining < 5:
            return None

        arena = spot.ltl_to_game(f, list(outputs))
        realizable = spot.solve_game(arena)
        if not realizable:
            return None

        best_aiger = None
        best_gates = current_gates  # Only beat current
        best_method = None
        encodings = ["isop", "ite", "both+dc", "both+ud+dc"]

        # Strategy 1: split mealy (default)
        remaining = timeout - (time.time() - start)
        if remaining > 2:
            split_mealy = spot.solved_game_to_split_mealy(arena)
            for enc in encodings:
                aiger_text, gates = try_aiger(split_mealy, enc)
                if gates is not None and gates < best_gates:
                    best_gates, best_aiger, best_method = gates, aiger_text, f'reopt-split+{enc}'

        # Strategy 2: simplify with minimize_lvl=2
        remaining = timeout - (time.time() - start)
        if remaining > 5:
            try:
                si = spot.synthesis_info()
                si.minimize_lvl = 2
                split2 = spot.solved_game_to_split_mealy(arena)
                spot.simplify_mealy_here(split2, si, False)
                for enc in encodings:
                    aiger_text, gates = try_aiger(split2, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'reopt-simplify2+{enc}'
            except Exception:
                pass

        # Strategy 3: simplify with minimize_lvl=3
        remaining = timeout - (time.time() - start)
        if remaining > 5:
            try:
                si = spot.synthesis_info()
                si.minimize_lvl = 3
                split3 = spot.solved_game_to_split_mealy(arena)
                spot.simplify_mealy_here(split3, si, False)
                for enc in encodings:
                    aiger_text, gates = try_aiger(split3, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'reopt-simplify3+{enc}'
            except Exception:
                pass

        # Strategy 4: minimize_mealy (unsplit)
        remaining = timeout - (time.time() - start)
        if remaining > 5:
            try:
                mealy = spot.solved_game_to_mealy(arena)
                min_m = spot.minimize_mealy(mealy, -1)
                for enc in encodings:
                    aiger_text, gates = try_aiger(min_m, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'reopt-minimize+{enc}'
            except Exception:
                pass

        # Strategy 5: minimize_mealy + simplify
        remaining = timeout - (time.time() - start)
        if remaining > 5:
            try:
                mealy = spot.solved_game_to_mealy(arena)
                min_m = spot.minimize_mealy(mealy, -1)
                si = spot.synthesis_info()
                si.minimize_lvl = 3
                spot.simplify_mealy_here(min_m, si, False)
                for enc in encodings:
                    aiger_text, gates = try_aiger(min_m, enc)
                    if gates is not None and gates < best_gates:
                        best_gates, best_aiger, best_method = gates, aiger_text, f'reopt-min+simp3+{enc}'
            except Exception:
                pass

        if best_aiger is not None:
            return {
                'aiger': best_aiger,
                'and_gates': best_gates,
                'method': best_method,
                'time': time.time() - start,
            }

    except Exception as e:
        pass

    return None


def main():
    from library.solutions import load_solutions, update_solution

    with open(REFERENCE_CSV) as f:
        reference = {r['instance']: r for r in csv.DictReader(f)}
    solutions = load_solutions()

    # Find improvable instances sorted by gap
    improvable = []
    for name, sol in solutions.items():
        if sol['status'] != 'realizable' or sol['and_gates'] <= 0:
            continue
        r = reference.get(name, {})
        ref_size = int(r.get('ref_size', -1))
        ni, no = int(r.get('n_inputs', 99)), int(r.get('n_outputs', 99))
        # Only try instances with moderate signal count (game construction must finish)
        if ni + no > 15:
            continue
        gap = sol['and_gates'] - max(ref_size, 0)
        if gap > 50:  # Only bother if gap is meaningful
            improvable.append((name, sol['and_gates'], ref_size, gap))

    improvable.sort(key=lambda x: -x[3])

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    targets = improvable[:limit]

    print(f"Re-optimizing top {len(targets)} improvable instances (timeout={timeout}s each)")
    improved = 0

    for i, (name, current_gates, ref_size, gap) in enumerate(targets):
        tlsf = INSTANCES_DIR / f"{name}.tlsf"
        if not tlsf.exists():
            continue

        print(f"  [{i+1}/{len(targets)}] {name}: {current_gates} gates (ref: {ref_size}, gap: {gap})...", end="", flush=True)
        t0 = time.time()
        result = resynthesize(tlsf, current_gates, timeout=timeout)

        if result:
            new_gates = result['and_gates']
            saved = current_gates - new_gates
            if update_solution(name, 'realizable', result['aiger'], result['method']):
                improved += 1
                print(f" -> {new_gates} gates (saved {saved}) [{result['time']:.1f}s]")
                # Log
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(EXPERIMENTS_LOG, "a") as f:
                    f.write(f"[{ts}] instance: {name} | approach: {result['method']} | status: realizable | and_gates: {new_gates} | time: {result['time']:.1f}s | notes: reopt from {current_gates}, saved {saved}\n")
            else:
                print(f" no improvement [{time.time()-t0:.1f}s]")
        else:
            print(f" failed [{time.time()-t0:.1f}s]")

    print(f"\nDone: improved {improved}/{len(targets)} instances")


if __name__ == "__main__":
    main()
