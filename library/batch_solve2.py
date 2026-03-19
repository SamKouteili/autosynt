"""Batch solver using subprocess parallelism (avoids macOS multiprocessing issues)."""

import csv
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTANCES_DIR = ROOT / "benchmarks" / "syntcomp-2025" / "instances"
REFERENCE_CSV = ROOT / "benchmarks" / "syntcomp-2025" / "reference.csv"
EXPERIMENTS_LOG = ROOT / "experiments.log"

sys.path.insert(0, str(ROOT))


def load_reference():
    with open(REFERENCE_CSV) as f:
        return {r['instance']: r for r in csv.DictReader(f)}


def solve_one_subprocess(instance_name, timeout=120):
    """Solve a single instance via subprocess call."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "library.solve_one", instance_name, str(timeout)],
            capture_output=True, text=True, timeout=timeout + 10,
            cwd=str(ROOT)
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return instance_name, json.loads(proc.stdout.strip())
        else:
            err = proc.stderr.strip()[:200] if proc.stderr else "unknown error"
            return instance_name, {"status": "error", "error": err, "time": 0}
    except subprocess.TimeoutExpired:
        return instance_name, {"status": "timeout", "time": timeout, "error": None}
    except Exception as e:
        return instance_name, {"status": "error", "error": str(e), "time": 0}


def log_experiment(instance, result):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = result['status']
    gates = result.get('and_gates', -1)
    gates_str = str(gates) if gates and gates >= 0 else 'N/A'
    elapsed = result.get('time', 0)
    method = result.get('method', '?')
    error = result.get('error', '')
    notes = f"{method}" + (f" | error: {error}" if error else "")
    line = f"[{ts}] instance: {instance} | approach: {method} | status: {status} | and_gates: {gates_str} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def batch_solve(instance_names, timeout=120, max_workers=8):
    from library.solutions import update_solution, mark_unrealizable

    total = len(instance_names)
    solved = 0
    new_solved = 0
    new_real = 0
    new_unreal = 0
    timeouts = 0
    errors = 0

    print(f"Batch: {total} instances, {max_workers} workers, timeout={timeout}s")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(solve_one_subprocess, name, timeout): name
            for name in instance_names
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                _, result = future.result(timeout=timeout + 30)
                solved += 1
                log_experiment(name, result)

                if result['status'] == 'realizable':
                    if update_solution(name, 'realizable', result.get('aiger'), result.get('method', '?')):
                        new_solved += 1
                        new_real += 1
                        gates = result.get('and_gates', -1)
                        print(f"  [R] {name}: {gates} gates [{result.get('time',0):.1f}s]")
                elif result['status'] == 'unrealizable':
                    if mark_unrealizable(name, result.get('method', '?')):
                        new_solved += 1
                        new_unreal += 1
                        print(f"  [U] {name} [{result.get('time',0):.1f}s]")
                elif result['status'] == 'timeout':
                    timeouts += 1
                else:
                    errors += 1

                if solved % 25 == 0:
                    print(f"  --- {solved}/{total} done, +{new_solved} new ({new_real}R/{new_unreal}U), {timeouts} timeouts ---")

            except Exception as e:
                errors += 1
                solved += 1

    print(f"\nDone: {solved}/{total}, +{new_solved} new ({new_real}R/{new_unreal}U), {timeouts} timeouts, {errors} errors")
    return new_solved


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--family", type=str, default=None)
    parser.add_argument("--status-filter", type=str, default=None)
    parser.add_argument("--max-signals", type=int, default=None)
    parser.add_argument("--min-signals", type=int, default=0)
    parser.add_argument("--skip-solved", action="store_true", default=True)
    parser.add_argument("--instances", nargs="*", default=None)
    args = parser.parse_args()

    from library.solutions import load_solutions

    reference = load_reference()
    solutions = load_solutions()

    if args.instances:
        names = args.instances
    else:
        names = list(reference.keys())

        if args.skip_solved:
            names = [n for n in names if n not in solutions]

        if args.family:
            names = [n for n in names if reference[n]['family'] == args.family]

        if args.status_filter:
            names = [n for n in names if reference[n]['status'] == args.status_filter]

        if args.max_signals:
            names = [n for n in names
                     if int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']) <= args.max_signals]

        if args.min_signals:
            names = [n for n in names
                     if int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']) >= args.min_signals]

    # Sort by total signals (easiest first)
    names.sort(key=lambda n: int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']))

    if not names:
        print("No instances to solve.")
        sys.exit(0)

    print(f"Selected {len(names)} instances")
    batch_solve(names, timeout=args.timeout, max_workers=args.workers)
