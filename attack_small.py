#!/usr/bin/env python3.14
"""Attack small unsolved instances (<=8 signals) with spot game approach + longer timeouts."""

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
PYTHON = "/opt/homebrew/bin/python3.14"

sys.path.insert(0, str(ROOT))


def solve_one(instance_name, timeout=240):
    """Solve via subprocess using python3.14 which has spot."""
    script = f'''
import sys, json, time
sys.path.insert(0, "{ROOT}")
from library.synth import solve_instance
result = solve_instance("{INSTANCES_DIR}/{instance_name}.tlsf", timeout={timeout})
print(json.dumps(result))
'''
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script],
            capture_output=True, text=True, timeout=timeout + 15,
            cwd=str(ROOT)
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.strip().split('\n')
            return instance_name, json.loads(lines[-1])
        else:
            err = proc.stderr.strip()[:200] if proc.stderr else "unknown"
            return instance_name, {"status": "error", "error": err, "time": 0}
    except subprocess.TimeoutExpired:
        return instance_name, {"status": "timeout", "time": timeout}
    except Exception as e:
        return instance_name, {"status": "error", "error": str(e), "time": 0}


def log_experiment(instance, result):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = result['status']
    gates = result.get('and_gates', -1)
    gates_str = str(gates) if gates and gates >= 0 else 'N/A'
    elapsed = result.get('time', 0)
    method = result.get('method', '?')
    notes = method
    line = f"[{ts}] instance: {instance} | approach: {method} | status: {status} | and_gates: {gates_str} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def main():
    from library.solutions import load_solutions, update_solution, mark_unrealizable

    # Load reference and solutions
    with open(REFERENCE_CSV) as f:
        reference = {r['instance']: r for r in csv.DictReader(f)}
    solutions = load_solutions()

    # Find unsolved instances with <= max_signals
    max_signals = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 240

    targets = []
    for name, info in reference.items():
        if name in solutions:
            continue
        ni, no = int(info['n_inputs']), int(info['n_outputs'])
        if ni + no <= max_signals:
            targets.append(name)

    targets.sort(key=lambda n: int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']))
    print(f"Attacking {len(targets)} small unsolved instances (signals<={max_signals}, timeout={timeout}s)")

    if not targets:
        print("Nothing to do.")
        return

    new_solved = 0
    done = 0
    workers = min(4, len(targets))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(solve_one, name, timeout): name for name in targets}
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                _, result = future.result(timeout=timeout + 30)
                log_experiment(name, result)

                if result['status'] == 'realizable':
                    if update_solution(name, 'realizable', result.get('aiger'), result.get('method', '?')):
                        new_solved += 1
                        print(f"  [R] {name}: {result.get('and_gates', -1)} gates [{result.get('time',0):.1f}s]")
                elif result['status'] == 'unrealizable':
                    if mark_unrealizable(name, result.get('method', '?')):
                        new_solved += 1
                        print(f"  [U] {name} [{result.get('time',0):.1f}s]")
                elif result['status'] == 'timeout':
                    print(f"  [T] {name} [{timeout}s]")
                else:
                    print(f"  [E] {name}: {result.get('error', '?')[:60]}")
            except Exception as e:
                print(f"  [X] {name}: {e}")

            if done % 10 == 0:
                print(f"  --- {done}/{len(targets)}, +{new_solved} new ---")

    print(f"\nDone: {done}/{len(targets)}, +{new_solved} new solutions")


if __name__ == "__main__":
    main()
