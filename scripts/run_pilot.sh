#!/usr/bin/env bash
# Rot Tax — registered pilot runner (v0.2), cross-provider (GPT + Claude).
# Loads keys from a gitignored .env (never committed), estimates cost, then runs the
# budget-fitting matrix and analyzes each model's output.
#
#   1) Create .env in the repo root:
#        OPENAI_API_KEY=sk-...
#        ANTHROPIC_API_KEY=sk-ant-...
#   2) bash scripts/run_pilot.sh            (interactive: asks before spending)
#      ROTTAX_YES=1 bash scripts/run_pilot.sh   (non-interactive)
#
# Per-provider credit pools (independent): GPT <= ~$200, Claude <= ~$50.
# Each run enforces its own --budget ceiling and ABORTS if exceeded.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi

GPT_LEVELS="5000,20000,50000,90000,120000"     # under GPT 128k limit
CLA_LEVELS="5000,20000,50000,90000,150000"     # Claude 200k allows 150k

echo "============================================================"
echo " ROT TAX PILOT — dry cost estimate first (no API calls)"
echo "============================================================"
echo "[GPT] gpt-4o-mini full grid:"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o-mini --budget 110 --estimate
echo "[GPT] gpt-4o strong-tier subset:"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o --primary-only \
        --items 3 --reps 6 --positions front,end --budget 90 --estimate
echo "[Claude] claude-haiku cross-provider arm:"
python3 -m harness.run_rotcurve --provider anthropic --model claude-haiku-4-5-20251001 \
        --primary-only --items 3 --reps 6 --positions front,end --levels "$CLA_LEVELS" \
        --budget 50 --estimate

if [ "${ROTTAX_YES:-}" != "1" ]; then
  read -r -p "Proceed with the REAL run? Spends real money. [y/N] " ok
  [ "$ok" = "y" ] || { echo "aborted."; exit 0; }
fi
[ -n "${OPENAI_API_KEY:-}" ] || { echo "ERROR: OPENAI_API_KEY not set (.env)."; exit 1; }
[ -n "${ANTHROPIC_API_KEY:-}" ] || { echo "ERROR: ANTHROPIC_API_KEY not set (.env)."; exit 1; }

echo "### ARM 1/3: gpt-4o-mini (full grid, workhorse) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o-mini --budget 110 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-4o-mini.jsonl --signals

echo "### ARM 2/3: gpt-4o (strong-tier confirmation subset) ###"
python3 -m harness.run_rotcurve --provider openai --model gpt-4o --primary-only \
        --items 3 --reps 6 --positions front,end --budget 90 --shuffle
python3 -m harness.analyze --input results/rot_raw__gpt-4o.jsonl --signals

echo "### ARM 3/3: claude-haiku (cross-provider arm, up to 150k) ###"
python3 -m harness.run_rotcurve --provider anthropic --model claude-haiku-4-5-20251001 \
        --primary-only --items 3 --reps 6 --positions front,end --levels "$CLA_LEVELS" \
        --budget 50 --shuffle
python3 -m harness.analyze --input results/rot_raw__claude-haiku-4-5-20251001.jsonl --signals

echo
echo "DONE. Raw data: results/rot_raw__*.jsonl | curves: results/rot_curve*.png"
echo "Spend logs: logs/spend__*.jsonl (each run enforced its own --budget ceiling)."
