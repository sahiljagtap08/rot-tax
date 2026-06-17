"""Unit tests for controlled context construction (v0.2). Offline, no API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.context_builder import (generate_substrate, build_needle, build_filler,
                                     assemble_trial, assert_invariants,
                                     K_EDIT_DISTRACT, K_TESTS_TEMPT)
from harness.models import estimate_tokens
from harness.probes import make_probes, gold_and_mockgold


def test_substrate_deterministic():
    a = generate_substrate(0, 42, 6, 5)
    b = generate_substrate(0, 42, 6, 5)
    assert a.probe_a_target.name == b.probe_a_target.name
    assert a.probe_a_target.nonce == b.probe_a_target.nonce
    assert a.edit_log == b.edit_log


def test_nonce_is_unmemorizable_token():
    a = generate_substrate(0, 42, 6, 5)
    # nonce must not be a natural-language literal; must be the NX-prefixed random token
    assert a.probe_a_target.nonce.startswith("NX") and len(a.probe_a_target.nonce) >= 8


def test_structured_load_invariant_in_T():
    # The whole difficulty-invariance fix: structured load count is independent of T.
    sub = generate_substrate(0, 42, 6, 5)
    for T in (5000, 50000, 150000):
        sB, _ = build_filler(sub, "B", T, "diverse", 42)
        sC, _ = build_filler(sub, "C", T, "diverse", 42)
        assert len(sB) == K_EDIT_DISTRACT
        assert len(sC) == K_TESTS_TEMPT
    assert_invariants(sub)  # must not raise


def test_neutral_volume_grows_with_T():
    sub = generate_substrate(0, 42, 6, 5)
    _, small = build_filler(sub, "A", 5000, "diverse", 42)
    _, big = build_filler(sub, "A", 50000, "diverse", 42)
    assert estimate_tokens("\n".join(big)) > estimate_tokens("\n".join(small)) * 3


def test_needle_present_contains_nonce_end_position():
    sub = generate_substrate(0, 42, 6, 5)
    probe = make_probes(sub)[0]
    trial = assemble_trial(sub, "A", probe.text, 5000, position="end",
                           composition="diverse", needle_mode="present", content_seed=42)
    content = trial.messages[0]["content"]
    assert sub.nonce_present in content       # the answer is in context
    assert sub.probe_a_target.name in content


def test_no_needle_control_excludes_answer():
    sub = generate_substrate(0, 42, 6, 5)
    probe = make_probes(sub)[0]
    trial = assemble_trial(sub, "A", probe.text, 50000, position="front",
                           composition="diverse", needle_mode="absent", content_seed=42)
    content = trial.messages[0]["content"]
    assert sub.nonce_present not in content   # control: answer is NOT recoverable


def test_counterfactual_gold_is_n2():
    sub = generate_substrate(0, 42, 6, 5)
    probe = make_probes(sub)[0]
    gold, _ = gold_and_mockgold(sub, probe, "counterfactual")
    assert gold == sub.nonce_counterfactual and gold != sub.nonce_stale


def test_distracting_filler_does_not_leak_target_nonce():
    sub = generate_substrate(0, 42, 6, 5)
    _, neutral = build_filler(sub, "A", 50000, "distracting", 42)
    blob = "\n".join(neutral)
    assert sub.nonce_present not in blob       # near-miss filler never states the target answer
    assert sub.probe_a_target.name not in blob


def test_position_changes_needle_location():
    sub = generate_substrate(0, 42, 6, 5)
    probe = make_probes(sub)[0]
    front = assemble_trial(sub, "A", probe.text, 50000, position="front", composition="diverse",
                           needle_mode="present", content_seed=42).messages[0]["content"]
    end = assemble_trial(sub, "A", probe.text, 50000, position="end", composition="diverse",
                         needle_mode="present", content_seed=42).messages[0]["content"]
    # in 'end', the needle (nonce) sits near the probe; in 'front' it sits near the top
    assert front.index(sub.nonce_present) < len(front) * 0.5
    assert end.index(sub.nonce_present) > len(end) * 0.5


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} context-builder tests passed.")
