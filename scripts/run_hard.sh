#!/usr/bin/env bash
# Rot Tax — HARD probe run (NoLiMa-style latent 2-hop, aggregation, conflicting instruction).
# Sized to the budget remaining after the easy run (~$128 OpenAI, ~$15 Anthropic).
#   ROTTAX_YES=1 bash scripts/run_hard.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
HARD="--probeset hard --comps diverse"

echo "=== HARD grid estimates ==="
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4-mini $HARD --modes present,absent --positions front,mid,end --items 3 --reps 8 --budget 80 --estimate
python3 -m harness.run_rotcurve --provider openai --model gpt-5.5 $HARD --modes present,absent --positions front,end --items 2 --reps 2 --budget 60 --estimate
python3 -m harness.run_rotcurve --provider anthropic --model claude-sonnet-4-6 $HARD --modes present --positions front,end --items 1 --reps 2 --budget 15 --estimate

if [ "${ROTTAX_YES:-}" != "1" ]; then
  read -r -p "Proceed with the REAL hard run (~\$115)? [y/N] " ok; [ "$ok" = "y" ] || { echo aborted; exit 0; }
fi

echo "### HARD A — gpt-5.4-mini (depth) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4-mini $HARD --modes present,absent --positions front,mid,end --items 3 --reps 8 --budget 80 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-5_4-mini__hard.jsonl --signals

echo "### HARD B — gpt-5.5 (frontier) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.5 $HARD --modes present,absent --positions front,end --items 2 --reps 2 --budget 60 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-5_5__hard.jsonl --signals

echo "### HARD C — claude-sonnet-4-6 (cross-provider) ###"
python3 -m harness.run_rotcurve --provider anthropic --model claude-sonnet-4-6 $HARD --modes present --positions front,end --items 1 --reps 2 --budget 15 --shuffle
python3 -m harness.analyze --input results/rot_raw__claude-sonnet-4-6__hard.jsonl --signals
echo "DONE (hard)."
