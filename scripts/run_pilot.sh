#!/usr/bin/env bash
# Rot Tax — registered pilot runner (v0.2).
# Loads keys from a gitignored .env (never committed), estimates cost, then runs the
# budget-fitting matrix and analyzes each model's output.
#
#   1) Create .env in the repo root:
#        OPENAI_API_KEY=sk-...
#        ANTHROPIC_API_KEY=sk-ant-...      # optional: enables the Claude cross-provider arm
#   2) bash scripts/run_pilot.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# load .env if present (keys only; .env is gitignored)
if [ -f .env ]; then set -a; . ./.env; set +a; fi

GPT_LEVELS="5000,20000,50000,90000,120000"     # under GPT 128k limit
CLA_LEVELS="5000,20000,50000,90000,150000"     # Claude 200k allows 150k

echo "============================================================"
echo " ROT TAX PILOT — dry cost estimate first (no API calls)"
echo "============================================================"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o-mini --estimate
python3 -m harness.run_rotcurve --provider openai --model gpt-4o --primary-only \
        --items 3 --reps 6 --positions front,end --estimate
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  python3 -m harness.run_rotcurve --provider anthropic --model claude-haiku-4-5-20251001 \
          --primary-only --items 3 --reps 6 --positions front,end --levels "$CLA_LEVELS" --estimate
fi

echo
read -r -p "Proceed with the REAL run? Spends real money. [y/N] " ok
[ "$ok" = "y" ] || { echo "aborted."; exit 0; }

if [ -z "${OPENAI_API_KEY:-}" ]; then echo "ERROR: OPENAI_API_KEY not set (.env)."; exit 1; fi

echo "### ARM 1/3: gpt-4o-mini (full grid) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o-mini --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-4o-mini.jsonl --signals

echo "### ARM 2/3: gpt-4o (primary-only confirmation subset) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o --primary-only \
        --items 3 --reps 6 --positions front,end --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-4o.jsonl --signals

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "### ARM 3/3: claude-haiku (cross-provider arm, up to 150k) ###"
  python3 -m harness.run_rotcurve --provider anthropic --model claude-haiku-4-5-20251001 \
          --primary-only --items 3 --reps 6 --positions front,end --levels "$CLA_LEVELS" --shuffle
  python3 -m harness.analyze --input results/rot_raw__claude-haiku-4-5-20251001.jsonl --signals
fi

echo
echo "DONE. Per-model raw data in results/rot_raw__*.jsonl, curves in results/rot_curve*.png."
echo "Each run independently enforces the \$200 budget ceiling (see logs/spend*.jsonl)."
