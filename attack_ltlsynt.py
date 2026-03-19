#!/usr/bin/env python3.14
"""Attack unsolved instances using ltlsynt directly with multiple strategies."""

import csv
import json
import sys
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

ROOT = Path(__file__).resolve().parent
INSTANCES_DIR = ROOT / "benchmarks" / "syntcomp-2025" / "instances"
REFERENCE_CSV = ROOT / "benchmarks" / "syntcomp-2025" / "reference.csv"
EXPERIMENTS_LOG = ROOT / "experiments.log"

sys.path.insert(0, str(ROOT))


def solve_ltlsynt(instance_name, timeout=60):
    """Try ltlsynt with multiple algorithm combos, return best result."""
    tlsf = str(INSTANCES_DIR / f"{instance_name}.tlsf")
    combos = [
        (["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--decompose=yes"], "ltlsynt-default+decompose"),
        (["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=lar", "--decompose=yes"], "ltlsynt-lar+decompose"),
        (["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=sd", "--decompose=yes"], "ltlsynt-sd+decompose"),
        (["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=ds"], "ltlsynt-ds"),
        (["ltlsynt", f"--tlsf={tlsf}", "--aiger", "--algo=ps"], "ltlsynt-ps"),
    ]
    per_timeout = max(10, timeout // len(combos))
    best = None

    for cmd, method in combos:
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=per_timeout)
            elapsed = time.time() - t0
            output = proc.stdout.strip()

            if "UNREALIZABLE" in output:
                return {"status": "unrealizable", "and_gates": -1, "method": method,
                        "time": elapsed, "aiger": None}
            elif "REALIZABLE" in output and "UNREALIZABLE" not in output:
                parts = output.split("\n", 1)
                aiger = parts[1] if len(parts) > 1 else None
                gates = -1
                if aiger:
                    try:
                        gates = int(aiger.strip().split('\n')[0].split()[5])
                    except:
                        pass
                result = {"status": "realizable", "and_gates": gates, "method": method,
                          "time": elapsed, "aiger": aiger}
                if best is None or (gates >= 0 and gates < best.get('and_gates', float('inf'))):
                    best = result
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

    return best or {"status": "timeout", "time": timeout}


def log_experiment(instance, result):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = result.get('status', '?')
    gates = result.get('and_gates', -1)
    gates_str = str(gates) if gates and gates >= 0 else 'N/A'
    elapsed = result.get('time', 0)
    method = result.get('method', '?')
    line = f"[{ts}] instance: {instance} | approach: {method} | status: {status} | and_gates: {gates_str} | time: {elapsed:.1f}s | notes: {method}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    from library.solutions import load_solutions, update_solution, mark_unrealizable

    with open(REFERENCE_CSV) as f:
        reference = {r['instance']: r for r in csv.DictReader(f)}
    solutions = load_solutions()

    min_sig = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    max_sig = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 90

    targets = []
    for name, info in reference.items():
        if name in solutions:
            continue
        ni, no = int(info['n_inputs']), int(info['n_outputs'])
        if min_sig <= ni + no <= max_sig:
            targets.append(name)

    targets.sort(key=lambda n: int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']))
    print(f"ltlsynt attack: {len(targets)} unsolved instances (signals {min_sig}-{max_sig}, timeout={timeout}s)")

    if not targets:
        print("Nothing to do.")
        return

    new_solved = 0
    done = 0
    workers = min(4, len(targets))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(solve_ltlsynt, name, timeout): name for name in targets}
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                result = future.result(timeout=timeout + 30)
                log_experiment(name, result)

                if result.get('status') == 'realizable':
                    if update_solution(name, 'realizable', result.get('aiger'), result.get('method', '?')):
                        new_solved += 1
                        print(f"  [R] {name}: {result.get('and_gates', -1)} gates [{result.get('time',0):.1f}s] ({result.get('method','')})")
                elif result.get('status') == 'unrealizable':
                    if mark_unrealizable(name, result.get('method', '?')):
                        new_solved += 1
                        print(f"  [U] {name} [{result.get('time',0):.1f}s] ({result.get('method','')})")
                elif result.get('status') == 'timeout':
                    pass  # silent
                else:
                    pass
            except Exception as e:
                pass

            if done % 20 == 0:
                print(f"  --- {done}/{len(targets)}, +{new_solved} new ---")

    print(f"\nDone: {done}/{len(targets)}, +{new_solved} new solutions")


if __name__ == "__main__":
    main()
