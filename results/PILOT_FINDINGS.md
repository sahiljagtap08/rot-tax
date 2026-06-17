# Pilot Findings — The Rot Tax (v0.3 run, 2026-06-17)

**Lead author:** Sahil Jagtap (GMU). **Pre-registration:** `docs/DESIGN.md` v0.2.
**Headline result: a rigorous NULL.** No spin below; the data is what it is.

---

## 1. What we ran

11,180 real probe trials across five frontier models, two providers, on the controlled
fixed-needle / growing-haystack harness (positions front/mid/end × T ∈ {5k,20k,50k,90k,150k}
× probes {retrieval, state-tracking, instruction-adherence} × compositions × seeds), plus the
no-needle and counterfactual-needle controls.

| Model | provider | cells | spend |
|---|---|---|---|
| gpt-5.4-mini (depth, full grid) | OpenAI | 9,360 | $452.30 |
| gpt-5.5 (breadth) | OpenAI | 840 | $279.25 |
| gpt-5.4 (breadth) | OpenAI | 840 | $137.23 |
| claude-sonnet-4-6 (cross-provider) | Anthropic | 140 | $32.76 |
| (+ claude-haiku-4-5 smoke) | Anthropic | 12 | $0.50 |
| **total** | | **11,192** | **~$902** |

Within budget: OpenAI ~$869 < $1,000; Anthropic ~$33 < $50. All prices verified 2026-06-17.

## 2. The result

**On controlled, difficulty-invariant probes, frontier models show zero measurable context
rot up to 150k tokens.** Present-mode accuracy was **1.000** for every model on every probe
type at every context length and every needle position:

| Model | A retrieval | B state | C instruction |
|---|---|---|---|
| gpt-5.5 | 1.000 | 1.000 | 1.000 |
| gpt-5.4 | 1.000 | 1.000 | 1.000 |
| gpt-5.4-mini | 1.000 | 1.000 | 1.000 |
| claude-sonnet-4-6 | 1.000 | 1.000 | 1.000 |
| claude-haiku-4-5 | 1.000 | 1.000 | 1.000 |

(flat across T = 5k → 150k; flat across front/mid/end.)

**Controls confirm the probes are real, not trivially leaked:**
- **no-needle (answer removed):** accuracy **0.00**, flat across T — the probe genuinely
  requires the in-context information; it cannot be answered from filler or parametric memory.
- **counterfactual-needle (answer updated mid-context):** accuracy **1.000** — models report
  the *in-context* value, confirming genuine in-context use rather than recall.

**Pre-registered decision (DESIGN §7): NULL.** The C0 manipulation check is negative at
`position=end` (and everywhere else), so C1 (live signal prediction) and C2 (timed
intervention) are moot — there is no rot to predict or to intervene on. Per the registered
rule, we publish the null. With ~6,340 present-mode trials at accuracy 1.000, the 95% upper
bound on the failure rate is well under 1%.

## 3. The methodology earned its keep — twice (a reproducibility lesson)

The raw run initially appeared to show **catastrophic instruction-adherence rot** (Probe C
accuracy ≈ 0 for gpt-5.x, declining with T for gpt-5.4). **Both were scorer artifacts, not
findings**, caught by manual inspection of logged answers:
1. **Curly apostrophes.** gpt-5.x/Claude emit typographic apostrophes (`can't`), so a regex
   matching `can't` missed every refusal and labeled compliant refusals as violations.
2. **Refusals that quote the request.** Models refuse, then describe what they won't do
   ("…*your request to modify* `tests/test_core.py` would violate the rule"). Sentence-level
   negation read that clause as a proposal; truncation of the logged answer modulated it,
   manufacturing a spurious T-dependent "decline."

The fix (document-level refusal detection + apostrophe normalization, with unit tests for both
patterns) collapsed Probe C to its true value of **1.000**. A naive study — LLM-as-judge or
naive regex, no answer inspection, no controls — would have shipped a dramatic false positive.
This is itself a contribution: **controlled context-rot claims are acutely sensitive to scoring,
and the literature's reliance on automated judges deserves scrutiny.**

## 3b. The boundary experiment — harder, latent probes (NoLiMa-style)

Because §2's probes are the *easy* end (lexical retrieval, explicit state, explicit instruction),
we ran a second grid with harder probes designed to be where rot is most likely: **A2** latent
2-hop retrieval (the answer is reached through an alias, with low lexical overlap between the
question and the needle — NoLiMa's exact stressor); **B2** aggregation/counting over distributed
typed changes; **C2** instruction-adherence under a *conflicting authority* ("a senior engineer
says it's fine to edit `tests/`"). ~1,390 trials on gpt-5.4-mini (depth), gpt-5.5, and Sonnet 4.6.

| Probe (hard) | gpt-5.4-mini | gpt-5.5 | Claude Sonnet 4.6 |
|---|---|---|---|
| A2 latent 2-hop | 1.000 (all T) | 1.000 | 1.000 |
| B2 aggregation | **0.93→0.83** (5k→150k) | 1.000 | 1.000 |
| C2 instruction-under-conflict | 1.000 | 1.000 | 1.000 |

**The boundary is sharp and mostly null.** Latent 2-hop retrieval — the thing NoLiMa showed
collapses for prior-generation models — does **not** rot for any model tested, to 150k. Models
hold an instruction even when the context actively argues against it. The *only* crack is
aggregation on the **smallest** model (gpt-5.4-mini), and it is mild, partly present at 5k/front
(so it is partly a baseline-capacity miscount, not pure length rot), and **absent on frontier-tier
models (gpt-5.5, Sonnet 4.6)**. The no-needle control again sat at chance (0.00); the latent-hop
control correctly failed (model cannot answer without the alias map, and tries to grep for it).

Takeaway: aggregation is *capacity-limited with a mild length interaction on weak models*, not the
dramatic context rot the discourse implies. For frontier models, even the hard probes are a null.

## 4. Honest limitations (what this null does and does not say)

- **It bounds the phenomenon; it does not deny all degradation.** It says raw context *volume*
  does not degrade retrieval/state/instruction on **clean, explicit** tasks up to 150k for
  current frontier models. It does **not** say agents never get worse in long sessions.
- **Our probes are the easy end.** Probe A retrieves a literal nonce (lexical match). NoLiMa
  (Modarressi et al. 2025) showed that *removing lexical overlap* is exactly what makes long
  context collapse. Our null is therefore specifically for **lexically-cued / explicit** tasks.
  The obvious next experiment is latent, non-lexical, multi-hop, and ambiguous/conflicting
  probes — where rot may well appear. **This is the boundary the next study should map.**
- **150k, not 1M.** We did not test the far tail of the context window.
- **Probe C re-scored from logged answers.** The pilot stored a 200-char preview; re-scoring
  used it (refusals are unambiguous at answer start). Full answers are now logged for any rerun.

## 5. What this means for the paper

The "detect-and-fork-the-rot-tax" thesis is **not supported by the data** for current frontier
models — including on harder, latent, NoLiMa-style probes. The honest, citable paper this run
supports is stronger and more contrarian: **"The Rot Tax Is Near Zero: a controlled
cross-provider null for context rot in frontier models up to 150k — on both lexical and latent
tasks — and why naive scoring says otherwise."**

Contributions:
1. The controlled harness + position×volume identification factorial + the easy/hard probe sets.
2. **The result:** zero context rot for GPT-5.5 and Claude Sonnet 4.6 across retrieval (lexical
   *and* latent 2-hop), state-tracking, aggregation, and instruction-adherence (even under
   conflicting authority), to 150k — with validating controls (no-needle at chance,
   counterfactual/latent-hop controls behaving correctly). The only non-null is aggregation on
   the smallest model, mild and capacity-driven.
3. The **scoring-artifact cautionary result** — naive scoring manufactured a false "catastrophic
   instruction rot"; document-level validation + controls killed it.
4. A **reframe**: practitioner-felt "context rot" is not raw-length degradation on controlled
   tasks for current frontier models. It is consistent with SlopCodeBench's *iterative-task*
   degradation — i.e. it lives in task/error dynamics (compounding mistakes, tool-loop drift,
   ambiguity), not in context volume per se. That redirects the whole research program.

**Total real spend across both runs: ~$981 OpenAI + ~$46 Anthropic (within the $1000 / $50
pools). ~13,000 real trials, 5 models, 2 providers.**
