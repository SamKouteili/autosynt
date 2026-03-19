"""Re-optimize existing realizable solutions to reduce AND gate counts.

Re-synthesizes instances using the improved solver with multiple encoding strategies.
"""

import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from library.batch_solve2 import solve_one_subprocess, log_experiment
from library.solutions import load_solutions, update_solution


def get_candidates(min_gates=1):
    """Find realizable solutions that might be improvable."""
    sols = load_solutions()
    candidates = []
    for name, sol in sols.items():
        if sol['status'] == 'realizable' and sol.get('and_gates', 0) >= min_gates:
            candidates.append((name, sol['and_gates']))
    candidates.sort(key=lambda x: -x[1])  # Biggest first (most room to improve)
    return candidates


def reoptimize(instance_names, timeout=120, max_workers=8):
    """Re-solve instances to try to get fewer AND gates."""
    total = len(instance_names)
    improved = 0
    total_savings = 0

    print(f"Re-optimizing {total} instances, {max_workers} workers, timeout={timeout}s")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(solve_one_subprocess, name, timeout): name
            for name in instance_names
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                _, result = future.result(timeout=timeout + 30)
                if result['status'] == 'realizable' and result.get('aiger'):
                    old_gates = load_solutions().get(name, {}).get('and_gates', float('inf'))
                    new_gates = result.get('and_gates', float('inf'))
                    if new_gates < old_gates:
                        if update_solution(name, 'realizable', result['aiger'], result['method']):
                            improved += 1
                            savings = old_gates - new_gates
                            total_savings += savings
                            print(f"  [+] {name}: {old_gates} -> {new_gates} (-{savings})")
                            log_experiment(name, result)
            except Exception:
                pass

    print(f"\nDone: {improved}/{total} improved, {total_savings} total gates saved")
    return improved


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--min-gates", type=int, default=10, help="Only re-optimize with at least this many gates")
    parser.add_argument("--max-count", type=int, default=None, help="Limit number of instances")
    args = parser.parse_args()

    candidates = get_candidates(min_gates=args.min_gates)
    names = [name for name, _ in candidates]

    if args.max_count:
        names = names[:args.max_count]

    if not names:
        print("No candidates for re-optimization.")
        sys.exit(0)

    print(f"Found {len(names)} candidates (min {args.min_gates} gates)")
    reoptimize(names, timeout=args.timeout, max_workers=args.workers)
