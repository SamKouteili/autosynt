#!/bin/bash
# Solve instances from a list file using ltlsynt with multiple strategies.
# Usage: ./solve_batch_shell.sh <instance_list> [timeout_per_strategy]
set -euo pipefail

LIST="${1:-/tmp/unsolved_small.txt}"
TIMEOUT="${2:-20}"
INST_DIR="benchmarks/syntcomp-2025/instances"
RESULTS="/tmp/solve_results.txt"
> "$RESULTS"

solve_one() {
    local inst="$1"
    local tlsf="${INST_DIR}/${inst}.tlsf"

    if [ ! -f "$tlsf" ]; then
        return
    fi

    # Try multiple strategies
    for args in \
        "--decompose=yes" \
        "--algo=lar --decompose=yes" \
        "--algo=sd --decompose=yes" \
        "--algo=ds" \
        "--algo=ps"; do

        local output
        output=$(timeout "${TIMEOUT}" ltlsynt --tlsf="$tlsf" --aiger $args 2>/dev/null) || continue

        if echo "$output" | head -1 | grep -q "UNREALIZABLE"; then
            echo "U|${inst}|ltlsynt ${args}" >> "$RESULTS"
            echo "[U] $inst"
            return
        elif echo "$output" | head -1 | grep -q "REALIZABLE"; then
            # Extract AIGER
            local aiger_file="/tmp/aiger_${inst}.aag"
            echo "$output" | tail -n +2 > "$aiger_file"
            local gates
            gates=$(head -1 "$aiger_file" | awk '{print $6}')
            echo "R|${inst}|ltlsynt ${args}|${gates}|${aiger_file}" >> "$RESULTS"
            echo "[R] $inst: ${gates}g"
            return
        fi
    done
}

export -f solve_one
export INST_DIR TIMEOUT RESULTS

echo "Solving $(wc -l < "$LIST") instances with timeout=${TIMEOUT}s per strategy"

# Run in parallel (4 workers)
cat "$LIST" | xargs -P 4 -I {} bash -c 'solve_one "$@"' _ {}

echo ""
echo "Results:"
echo "  Unrealizable: $(grep -c '^U|' "$RESULTS" 2>/dev/null || echo 0)"
echo "  Realizable: $(grep -c '^R|' "$RESULTS" 2>/dev/null || echo 0)"
