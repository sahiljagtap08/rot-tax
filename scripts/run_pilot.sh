#!/usr/bin/env bash
# Rot Tax — registered pilot runner (v0.3), two-track cross-provider design.
# Loads keys from a gitignored .env, estimates cost, then runs the matrix and analyzes each arm.
#
#   1) .env in repo root:  OPENAI_API_KEY=...   ANTHROPIC_API_KEY=...
#   2) bash scripts/run_pilot.sh           (interactive)
#      ROTTAX_YES=1 bash scripts/run_pilot.sh   (non-interactive)
#
# Credit pools (independent, enforced per-run via --budget):  OpenAI <= $1000,  Anthropic <= $50.
#
# TRACK A (depth, high-N backbone) -> full grid on gpt-5.4-mini  (C1 / identification / signals).
# TRACK B (breadth, frontier credibility) -> decisive subset (front+end x present+absent x all T
#   x diverse) on gpt-5.5, gpt-5.4 (OpenAI) and claude-sonnet-4-6 (cross-provider).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi

BR="--comps diverse --modes present,absent --positions front,end"   # breadth-subset shape

echo "============================================================"
echo " ROT TAX PILOT v0.3 — dry cost estimate (no API calls)"
echo "============================================================"
echo "[A depth ] gpt-5.4-mini full grid:"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4-mini --budget 520 --estimate
echo "[B breadth] gpt-5.5:"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.5 $BR --items 3 --reps 8 --budget 300 --estimate
echo "[B breadth] gpt-5.4:"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4 $BR --items 3 --reps 8 --budget 150 --estimate
echo "[B cross  ] claude-sonnet-4-6:"
python3 -m harness.run_rotcurve --provider anthropic --model claude-sonnet-4-6 $BR --items 2 --reps 2 --budget 50 --estimate

if [ "${ROTTAX_YES:-}" != "1" ]; then
  read -r -p "Proceed with the REAL run (~\$900 across both providers)? [y/N] " ok
  [ "$ok" = "y" ] || { echo "aborted."; exit 0; }
fi
[ -n "${OPENAI_API_KEY:-}" ] || { echo "ERROR: OPENAI_API_KEY not set (.env)."; exit 1; }
[ -n "${ANTHROPIC_API_KEY:-}" ] || { echo "ERROR: ANTHROPIC_API_KEY not set (.env)."; exit 1; }

echo "### TRACK A — gpt-5.4-mini (full grid, depth backbone) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4-mini --budget 520 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-5_4-mini.jsonl --signals

echo "### TRACK B1 — gpt-5.5 (frontier breadth) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.5 $BR --items 3 --reps 8 --budget 300 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-5_5.jsonl --signals

echo "### TRACK B2 — gpt-5.4 (frontier breadth) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-5.4 $BR --items 3 --reps 8 --budget 150 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-5_4.jsonl --signals

echo "### TRACK B3 — claude-sonnet-4-6 (cross-provider breadth) ###"
python3 -m harness.run_rotcurve --provider anthropic --model claude-sonnet-4-6 $BR --items 2 --reps 2 --budget 50 --shuffle
python3 -m harness.analyze --input results/rot_raw__claude-sonnet-4-6.jsonl --signals

echo
echo "DONE. Raw: results/rot_raw__*.jsonl | curves: results/rot_curve*.png | spend: logs/spend__*.jsonl"
