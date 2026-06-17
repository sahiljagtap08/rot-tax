# The Rot Tax

A research harness measuring **context rot in agentic-coding sessions**: whether a coding
agent's ability to use information *already in its context* degrades as session context
accumulates — holding task difficulty exactly constant — and what a timed intervention
recovers.

> **Lead author:** Sahil Jagtap (George Mason University) · sjagtap2@gmu.edu · jagtap.tech

This is **empirical work**. Correctness and reproducibility matter more than speed. No result
in this repository is ever fabricated or interpolated; numbers come only from real runs, and
mock/test artifacts are explicitly suffixed `.MOCK.` and never reported as findings.

## What it does (the one question)

> Does probe accuracy fall as accumulated session tokens climb, with task difficulty held
> constant via fixed-needle / growing-haystack probe injection?

See `docs/DESIGN.md` for the frozen pre-registration (claim, hypotheses, confound control,
operational definitions, statistics, and the GO/WEAK/NULL decision rule).

## Layout

```
config.yaml            run/model/experiment/pricing config (no science hard-coded in source)
docs/DESIGN.md         pre-registration (frozen before data collection)
harness/               the experimental apparatus
  config.py            typed config loader
  costs.py             per-call token+USD tracker with hard budget ABORT
  logging_utils.py     one-JSONL-line-per-event structured logger
  models.py            provider wrapper (anthropic | openai | mock) with exact token usage
  context_builder.py   controlled, seeded construction of agentic-session contexts
  probes.py            the 3 fixed-difficulty probes (A retrieval, B state, C instruction)
  scorers.py           automatic scorers (B & C mechanical; A validated model-judge)
  signals.py           cheap live-signal extractors (for the detector validation)
  run_rotcurve.py      Phase 2 runner -> results/rot_raw.jsonl
  analyze.py           stats + plots -> results/rot_curve.png
tests/                 unit tests (offline, no API): scorers + context builder
results/  logs/        outputs
```

## Quick start

```bash
pip install -r requirements.txt

# 1) Offline sanity: prove the plumbing works with a MOCK model (no key, no money)
python -m harness.run_rotcurve --provider mock --quick
python -m harness.analyze --input results/rot_raw.MOCK.jsonl   # prints MOCK banner

# 2) Real pilot (requires a key + budget):
export ANTHROPIC_API_KEY=...            # or OPENAI_API_KEY
python -m harness.run_rotcurve --provider anthropic
python -m harness.analyze --input results/rot_raw.jsonl
```

The runner streams spend to `logs/spend.jsonl` and **aborts** if `budget_usd_ceiling` is hit.

## Status

Harness + pre-registration complete and unit-tested offline. Real data collection is gated on
an API key and budget approval (see the project notes). The mock path exists only to verify
plumbing, never to produce findings.
