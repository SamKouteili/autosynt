"""Batch solver: solve multiple instances in parallel using multiprocessing."""

import csv
import json
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

# Paths
ROOT = Path(__file__).resolve().parent.parent
INSTANCES_DIR = ROOT / "benchmarks" / "syntcomp-2025" / "instances"
REFERENCE_CSV = ROOT / "benchmarks" / "syntcomp-2025" / "reference.csv"
EXPERIMENTS_LOG = ROOT / "experiments.log"


def load_reference():
    """Load reference.csv into dict keyed by instance name."""
    with open(REFERENCE_CSV) as f:
        return {r['instance']: r for r in csv.DictReader(f)}


def get_unsolved(reference, solutions):
    """Get list of unsolved instance names."""
    return [name for name in reference if name not in solutions]


def get_improvable(reference, solutions):
    """Get realizable instances where we might improve AND gate count."""
    improvable = []
    for name, sol in solutions.items():
        if sol['status'] == 'realizable':
            ref = reference.get(name, {})
            ref_size = int(ref.get('ref_size', -1))
            if ref_size >= 0 and sol['and_gates'] > ref_size:
                improvable.append((name, sol['and_gates'], ref_size))
    return sorted(improvable, key=lambda x: x[1] - x[2], reverse=True)


def solve_one(instance_name, timeout=120):
    """Solve a single instance. Must be picklable for multiprocessing."""
    from library.synth import solve_instance
    tlsf_path = INSTANCES_DIR / f"{instance_name}.tlsf"
    if not tlsf_path.exists():
        return instance_name, {'status': 'error', 'error': 'File not found', 'time': 0}
    result = solve_instance(tlsf_path, timeout=timeout)
    return instance_name, result


def log_experiment(instance, result):
    """Append to experiments.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = result['status']
    gates = result.get('and_gates', -1)
    gates_str = str(gates) if gates >= 0 else 'N/A'
    elapsed = result.get('time', 0)
    method = result.get('method', '?')
    error = result.get('error', '')
    notes = f"{method}" + (f" | error: {error}" if error else "")
    line = f"[{ts}] instance: {instance} | approach: {method} | status: {status} | and_gates: {gates_str} | time: {elapsed:.1f}s | notes: {notes}\n"
    with open(EXPERIMENTS_LOG, "a") as f:
        f.write(line)


def batch_solve(instance_names, timeout=120, max_workers=8):
    """Solve instances in parallel, updating solutions as we go."""
    sys.path.insert(0, str(ROOT))
    from library.solutions import load_solutions, update_solution, mark_unrealizable

    total = len(instance_names)
    solved = 0
    new_solved = 0
    errors = 0

    print(f"Batch solving {total} instances with {max_workers} workers, timeout={timeout}s")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(solve_one, name, timeout): name
            for name in instance_names
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                _, result = future.result(timeout=timeout + 30)
                solved += 1
                log_experiment(name, result)

                if result['status'] == 'realizable':
                    if update_solution(name, 'realizable', result['aiger'], result['method']):
                        new_solved += 1
                        gates = result['and_gates']
                        print(f"  [+] {name}: REALIZABLE ({gates} gates) [{result['time']:.1f}s]")
                elif result['status'] == 'unrealizable':
                    if mark_unrealizable(name, result['method']):
                        new_solved += 1
                        print(f"  [+] {name}: UNREALIZABLE [{result['time']:.1f}s]")
                elif result['status'] == 'timeout':
                    pass  # silent on timeout
                else:
                    errors += 1
                    if result.get('error'):
                        print(f"  [!] {name}: {result['error'][:80]}")

                if solved % 50 == 0:
                    print(f"  Progress: {solved}/{total} done, {new_solved} new solutions")

            except Exception as e:
                errors += 1
                solved += 1

    print(f"\nDone: {solved}/{total} attempted, {new_solved} new solutions, {errors} errors")
    return new_solved


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--family", type=str, default=None)
    parser.add_argument("--status-filter", type=str, default=None,
                        help="Filter by known status: realizable, unrealizable, unknown")
    parser.add_argument("--max-signals", type=int, default=None,
                        help="Max total signals (inputs+outputs)")
    parser.add_argument("--skip-solved", action="store_true", default=True)
    parser.add_argument("--instances", nargs="*", default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
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

    # Sort by total signals (easiest first)
    names.sort(key=lambda n: int(reference[n]['n_inputs']) + int(reference[n]['n_outputs']))

    if not names:
        print("No instances to solve.")
        sys.exit(0)

    print(f"Selected {len(names)} instances")
    batch_solve(names, timeout=args.timeout, max_workers=args.workers)
