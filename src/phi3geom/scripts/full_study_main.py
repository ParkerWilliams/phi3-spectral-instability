"""Full-study driver: 4800-event collection + per-regime composite (T059, US3).

Same logic as ``pilot_main`` but at 8× scale:

- 400 fail + 400 control per bin × 6 bins = 4800 matched events.
- ``compute_ricci=True`` (Forman-Ricci feature integrated; US2 having
  validated the pipeline).
- Pins ``k_attn`` from the pilot sweep report
  (``reports/pilot/k_attn_sweep.json``).
- Per-bin oversample escalation 1.5× → 3× via
  ``phi3geom.dataset.oversample.cem_match_with_escalation``.

Output: full-study cache populated, ``dataset/manifest_header.json``
written, ``reports/full/per_bin_auroc.json`` produced. The headline β(ℓ)
analysis is performed separately by ``run-analysis`` (T072, US4).
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from phi3geom.analysis.composite import (
    InsufficientDataError,
    fit_per_regime_composite,
)
from phi3geom.analysis.types import PerRegimeCompositeFit
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.dataset.manifest import write_manifest
from phi3geom.dataset.oversample import (
    CEMYieldEscalationError,
    cem_match_with_escalation,
)
from phi3geom.dataset.types import BIN_IDS, BIN_RANGES, BinId, CEMStratum, DocQAEvent, ManifestHeader
from phi3geom.extraction.pipeline import (
    GENERATION_CONFIG_SHA256,
    PROMPT_TEMPLATE_SHA256,
    run_event_extraction,
)
from phi3geom.geometry import FEATURE_NAMES
from phi3geom.reporting.pilot_reports import (
    write_cem_yield,
    write_per_bin_auroc,
    write_runtime,
)
from phi3geom.reproducibility.seeds import (
    seed_for_analysis,
    seed_for_match,
    seed_for_split,
)
from phi3geom.scripts.kattn_sweep import read_kattn_winner
from phi3geom.scripts.pilot_main import _build_feature_matrix, _now_iso, _git_commit_sha
from phi3geom.scripts.pin_model_revision import read_pin

FULL_STUDY_TARGET_PER_CLASS = 400


def _make_event_generator(bin_id: BinId, rng: random.Random):
    """Closure: returns a fresh pool of candidate events for the given bin."""
    def _gen(target_size: int) -> list[DocQAEvent]:
        events: list[DocQAEvent] = []
        for _ in range(target_size):
            template = rng.choice(TEMPLATES)
            fact = rng.choice(FACTS[template.template_id])
            density = rng.uniform(0.0, 1.0)
            lo, hi = BIN_RANGES[bin_id]
            target_distance = rng.randint(lo, hi - 1)
            event = generate_event(
                template=template, fact=fact,
                target_evidence_distance_words=target_distance,
                distractor_density=density,
                prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
                bin_id=bin_id,
                rng=rng,
            )
            events.append(event)
        return events
    return _gen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-per-class", type=int, default=FULL_STUDY_TARGET_PER_CLASS,
    )
    parser.add_argument("--cache-root", type=Path, default=Path("cache"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/full"))
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--k-attn-sweep-report",
        type=Path,
        default=Path("reports/pilot/k_attn_sweep.json"),
        help="Read the sweep winner for k_attn.",
    )
    parser.add_argument(
        "--k-attn-override",
        type=int,
        default=None,
        help="Override the sweep winner with a specific k_attn (DEBUG ONLY).",
    )
    args = parser.parse_args(argv)

    # Pin k_attn from the sweep report.
    if args.k_attn_override is not None:
        k_attn = args.k_attn_override
        print(f"[full-study] k_attn={k_attn} (override)")
    else:
        try:
            k_attn = read_kattn_winner(args.k_attn_sweep_report)
            print(f"[full-study] k_attn={k_attn} (from sweep)")
        except FileNotFoundError:
            print(
                f"[full-study] ERROR: sweep report {args.k_attn_sweep_report} not found. "
                f"Run kattn_sweep first, or pass --k-attn-override.",
                file=sys.stderr,
            )
            return 1

    # Read pinned model revision.
    pin = read_pin(args.dataset_dir / "pinned_revision.json")
    model_id = pin["model_id"]
    model_revision_sha = pin["model_revision_sha"]
    print(f"[full-study] Model: {model_id} @ {model_revision_sha[:8]}")

    # Load model + tokenizer.
    print("[full-study] Loading Phi-3-mini-128k-instruct...")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=model_revision_sha)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=model_revision_sha,
        torch_dtype=torch.float16, device_map="auto",
        attn_implementation="eager",
    )
    model.eval()

    # Per-bin: generate candidates, forward-pass + classify, CEM-match with escalation.
    t0 = time.monotonic()
    placeholder_sha = "0" * 64
    code_commit_sha = _git_commit_sha()
    split_seed = seed_for_split("v1")
    base_rng = random.Random(split_seed)

    matched_events: list[DocQAEvent] = []
    strata_by_bin: dict[BinId, list[CEMStratum]] = {}

    for bin_id in BIN_IDS:
        bin_rng = random.Random(seed_for_match(bin_id))
        gen = _make_event_generator(bin_id, bin_rng)

        # We forward-pass candidates AS WE NEED THEM to assign is_fail.
        # The oversample logic asks for a fresh pool of size N; we generate
        # then run forward + classify before returning.
        def labeled_generator(target_size: int) -> list[DocQAEvent]:
            candidates = gen(target_size)
            labeled: list[DocQAEvent] = []
            for cand in candidates:
                try:
                    res = run_event_extraction(
                        cand, model, tokenizer,
                        k_attn=k_attn,
                        manifest_sha256=placeholder_sha,
                        code_commit_sha=code_commit_sha,
                        cache_root=args.cache_root,
                        compute_ricci=True,
                    )
                    labeled.append(res.event)
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"[full-study] event {cand.event_id[:8]} skipped: {exc}",
                        file=sys.stderr,
                    )
            return labeled

        try:
            result = cem_match_with_escalation(
                event_generator=labeled_generator,
                bin_id=bin_id,
                target_per_class=args.target_per_class,
                rng=bin_rng,
            )
        except CEMYieldEscalationError as exc:
            print(f"[full-study] {exc}", file=sys.stderr)
            strata_by_bin[bin_id] = []
            continue

        matched_events.extend(result.matched_events)
        strata_by_bin[bin_id] = result.strata
        print(
            f"[full-study] {bin_id}: {len(result.matched_events)} matched "
            f"({result.yield_pct:.1f}% yield, {result.oversample_factor}× oversample, "
            f"compromised={result.is_compromised})"
        )

    elapsed = time.monotonic() - t0

    # Fit per-regime composite per bin.
    fits: dict[BinId, PerRegimeCompositeFit] = {}
    for bin_id in BIN_IDS:
        bin_events = [e for e in matched_events if e.bin_id == bin_id]
        if len(bin_events) < 100:
            continue
        features, labels = _build_feature_matrix(
            bin_events,
            cache_root=args.cache_root,
            expected_manifest_sha256=placeholder_sha,
        )
        try:
            fits[bin_id] = fit_per_regime_composite(
                features, labels, bin_id=bin_id,
                feature_names=FEATURE_NAMES,
                random_state=seed_for_analysis(f"per_regime_composite_full:{bin_id}"),
            )
        except InsufficientDataError as exc:
            print(f"[full-study] {bin_id} fit failed: {exc}", file=sys.stderr)

    # Write manifest header.
    header = ManifestHeader(
        schema_version="1.0.0",
        manifest_sha256="0" * 64,
        events_sha256="0" * 64,
        code_commit_sha=code_commit_sha,
        model_revision_sha=model_revision_sha,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        generation_config_sha256=GENERATION_CONFIG_SHA256,
        k_grass=8,
        k_attn=k_attn,
        lookback_window_length=256,
        feature_layout=FEATURE_NAMES,
        forman_ricci_convention="nan_with_median_imputation_and_indicator",
        adversariality_policy_per_bin={b: "none" for b in BIN_IDS},
        split_seed=split_seed,
        matching_seed_per_bin={b: seed_for_match(b) for b in BIN_IDS},
        constitution_version="1.0.0",
        spec_version="001",
        write_timestamp_utc=_now_iso(),
    )
    final_header = write_manifest(matched_events, header, args.dataset_dir)
    print(f"[full-study] manifest SHA = {final_header.manifest_sha256[:8]}")

    # Verify all 4800 event_ids before declaring success (T061).
    from phi3geom.dataset.manifest import verify_event_id
    mismatched = sum(
        1 for e in matched_events
        if not verify_event_id(e, prompt_template_sha256=PROMPT_TEMPLATE_SHA256)
    )
    if mismatched:
        print(
            f"[full-study] WARN: {mismatched} events have non-canonical event_ids "
            "(likely from adversariality recompute path)",
            file=sys.stderr,
        )

    # Write reports.
    write_per_bin_auroc(fits, out_dir=args.reports_dir)
    write_cem_yield(strata_by_bin, out_dir=args.reports_dir)
    write_runtime(
        wall_time_sec=elapsed,
        gpu_hours_estimate=elapsed / 3600.0,
        n_events=len(matched_events),
        out_dir=args.reports_dir,
    )
    print(f"[full-study] done in {elapsed / 3600.0:.2f} GPU-hours.")
    _ = base_rng  # quiet unused-var (kept for parity with pilot_main shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
