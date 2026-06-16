"""Pilot driver: 600-event end-to-end pipeline (T046, US1 MVP).

Generates ~150 candidate events per bin (oversampled so CEM matching can hit
50/class), runs Phi-3 forward passes, applies EM normalization, CEM-matches
within bin, runs feature extraction on matched events, fits ONE pooled
distance-blind detector over all matched events (Principle III, v2.0.0),
writes the pilot reports (pooled AUROC headline + distance/confound
diagnostics + ops).

This script is the driver for ``scripts/run_pilot.sh``. It expects:

- ``dataset/pinned_revision.json`` — written by ``pin-model-revision``.
- HuggingFace credentials configured.
- CUDA GPU available with ≥16 GB VRAM (Phi-3-mini-128k loads at fp16).

Per Constitution Principle V, deviations from the pilot recipe go through
``/speckit-specify``, not through script edits.
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from phi3geom.analysis.pooled_detector import fit_pooled_detector
from phi3geom.dataset.adversarial import apply_adversariality
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.dataset.manifest import write_manifest
from phi3geom.dataset.matching import MatchingFailedError, cem_match
from phi3geom.dataset.types import BIN_IDS, BIN_RANGES, BinId, CEMStratum, DocQAEvent, ManifestHeader
from phi3geom.extraction.pipeline import (
    GENERATION_CONFIG_SHA256,
    PROMPT_TEMPLATE_SHA256,
    run_event_extraction,
)
from phi3geom.geometry import FEATURE_NAMES
from phi3geom.reporting.pilot_reports import write_pilot_summary
from phi3geom.reproducibility.seeds import (
    seed_for_analysis,
    seed_for_match,
    seed_for_split,
)
from phi3geom.scripts.pin_model_revision import read_pin
from phi3geom.storage.cache import try_load_cached_event

PILOT_CANDIDATES_PER_BIN = 150  # ~1.5× the 50/class × 2 = 100-event target
PILOT_TARGET_PER_CLASS = 50


def _git_commit_sha() -> str:
    """Resolve git HEAD; fall back to 'unknown' outside a checkout."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_dur(seconds: float) -> str:
    """Format a duration as 'Xd Yh Zm Ws' (omits leading zero units)."""
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d > 0:
        return f"{d}d {h}h {m}m {s}s"
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _sample_evidence_distance_words(bin_id: BinId, rng: random.Random) -> int:
    """Pick a random target word distance within ``bin_id``'s range.

    NOTE: this is an approximation; the tokenizer's actual token count will
    be close but not identical. The exact bin assignment is verified by the
    pipeline at extraction time.
    """
    lo, hi = BIN_RANGES[bin_id]
    return rng.randint(lo, hi - 1)


def _generate_candidate_events(
    *,
    n_per_bin: int,
    rng: random.Random,
    prompt_template_sha256: str,
    adversariality: str = "none",
    n_adversarial: int = 3,
) -> list[DocQAEvent]:
    candidates: list[DocQAEvent] = []
    for bin_id in BIN_IDS:
        for _ in range(n_per_bin):
            template = rng.choice(TEMPLATES)
            fact = rng.choice(FACTS[template.template_id])
            density = rng.uniform(0.0, 1.0)
            target_distance = _sample_evidence_distance_words(bin_id, rng)
            event = generate_event(
                template=template,
                fact=fact,
                target_evidence_distance_words=target_distance,
                distractor_density=density,
                prompt_template_sha256=prompt_template_sha256,
                bin_id=bin_id,
                rng=rng,
            )
            if adversariality != "none":
                event = apply_adversariality(
                    event, adversariality, rng=rng, n_adversarial=n_adversarial,
                )
            candidates.append(event)
    return candidates


def _build_feature_matrix(
    events: list[DocQAEvent], *,
    cache_root: Path,
    expected_manifest_sha256: str,
) -> tuple[Any, Any]:
    """Read F_summary tensors and reduce to a per-event feature vector.

    For the pilot we use the per-event MEAN over the 32 layers × 32 heads ×
    7 features as the composite logistic's input — a simple aggregate that
    avoids overfitting in the small pilot. The full study uses richer
    per-bin spine FPC scores added during US4.
    """
    import numpy as np
    from phi3geom.storage.cache import read_F_summary

    feature_matrix = np.empty((len(events), 7), dtype=np.float64)
    labels = np.empty((len(events),), dtype=bool)
    for i, event in enumerate(events):
        arr = read_F_summary(
            event.event_id,
            expected_manifest_sha256=expected_manifest_sha256,
            cache_root=cache_root,
        )
        # arr shape (32, 32, N_FEATURES, 5) — take the mean stat (axis=3 index 0)
        mean_stat = arr[..., 0]  # (32, 32, 7)
        # Average over (layer, head) → (7,)
        feature_matrix[i] = mean_stat.astype(np.float64).mean(axis=(0, 1))
        labels[i] = event.is_fail
    return feature_matrix, labels


def _maybe_build_checkpoint_config(args):
    """Build a CheckpointConfig if --experiment-branch is set; else return None.

    Raises a clear RuntimeError before any expensive work if the PAT env var
    is missing or the origin remote isn't an HTTPS URL.
    """
    if not args.experiment_branch:
        return None
    import os

    from phi3geom.checkpointing import ARTIFACT_DIR_NAME, CheckpointConfig

    token = os.environ.get(args.github_token_env)
    if not token:
        raise RuntimeError(
            f"--experiment-branch set but env var ${args.github_token_env} is empty. "
            f"Export a fine-grained GitHub PAT (repo scope) before running."
        )
    remote_url = args.remote_url
    if remote_url is None:
        remote_url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True
        ).strip()
    if not remote_url.startswith("https://"):
        raise RuntimeError(
            f"Remote URL must be HTTPS for PAT auth; got {remote_url!r}. "
            f"Fix: git remote set-url origin https://github.com/<owner>/<repo>.git"
        )
    repo_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    return CheckpointConfig(
        branch=args.experiment_branch,
        token=token,
        remote_url=remote_url,
        cache_root=args.cache_root,
        artifact_root=repo_root / ARTIFACT_DIR_NAME,
        repo_root=repo_root,
    )


def _do_checkpoint(
    config,
    *,
    event_ids,
    processed: int,
    total: int,
    resumed: int,
    log_path,
    reports_dir,
    message: str | None = None,
) -> None:
    """Push one checkpoint. Logs the outcome but never raises into the loop."""
    from phi3geom.checkpointing import checkpoint

    msg = message or f"ckpt: {processed}/{total} events (resumed={resumed})"
    progress = {
        "events_processed": processed,
        "events_total": total,
        "events_resumed": resumed,
    }
    try:
        pushed = checkpoint(
            config,
            event_ids=event_ids,
            progress=progress,
            log_path=log_path if log_path.is_file() else None,
            extra_report_dir=reports_dir if reports_dir.is_dir() else None,
            message=msg,
        )
    except subprocess.CalledProcessError as exc:
        # Don't kill the run on a transient push failure — log + continue.
        # Next checkpoint will pick up the same staged data.
        print(f"[pilot] checkpoint FAILED ({exc}); continuing", file=sys.stderr)
        return
    if pushed:
        print(f"[pilot] checkpoint pushed: {msg}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-ricci",
        action="store_true",
        help="Enable Forman-Ricci feature integration (US2). Default: spectral-only baseline (US1).",
    )
    parser.add_argument("--k-attn", type=int, default=16, help="Attention-graph sparsification cutoff.")
    parser.add_argument("--cache-root", type=Path, default=Path("cache"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/pilot"))
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--n-per-bin",
        type=int,
        default=PILOT_CANDIDATES_PER_BIN,
        help="Candidate events per bin before CEM matching.",
    )
    parser.add_argument(
        "--target-per-class",
        type=int,
        default=PILOT_TARGET_PER_CLASS,
        help="Target matched events per class per bin.",
    )
    # Adversariality (raise the failure rate above the corpus's `none` baseline).
    parser.add_argument(
        "--adversariality",
        choices=["none", "lexical", "sibling_entity", "self_contradiction"],
        default="none",
        help=(
            "Distractor adversariality policy applied to every candidate. "
            "`sibling_entity` injects same-predicate, different-subject sentences "
            "(strongest existing lever) — recommended when `none` produces too "
            "few failures for CEM matching."
        ),
    )
    parser.add_argument(
        "--n-adversarial",
        type=int,
        default=3,
        help="Number of adversarial sentences injected per event. Default: 3.",
    )
    # Corpus selector — `synthetic` is the original Wikidata-template generator;
    # `hotpotqa` pulls from the HuggingFace HotpotQA dataset (multi-hop QA where
    # Phi-3-mini's ~30-40% EM gives a usable natural failure rate).
    parser.add_argument(
        "--corpus",
        choices=["synthetic", "hotpotqa"],
        default="synthetic",
        help="Candidate-event corpus. Default: synthetic (low natural fail rate).",
    )
    parser.add_argument(
        "--hotpotqa-split",
        type=str,
        default="train",
        help="HotpotQA split to draw from when --corpus=hotpotqa. Default: train.",
    )
    # Resilient-checkpoint args (optional; enabled by passing --experiment-branch).
    parser.add_argument(
        "--experiment-branch",
        type=str,
        default=None,
        help="Git branch to checkpoint progress to. Enables resume-on-restart.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Push a checkpoint after every N processed events. Default: 25.",
    )
    parser.add_argument(
        "--remote-url",
        type=str,
        default=None,
        help="Git remote HTTPS URL for checkpoints. Default: `git remote get-url origin`.",
    )
    parser.add_argument(
        "--github-token-env",
        type=str,
        default="GITHUB_TOKEN",
        help="Name of the env var holding the GitHub PAT. Default: GITHUB_TOKEN.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("reports/pilot_run.log"),
        help="Pilot log path to mirror into each checkpoint. Default: reports/pilot_run.log",
    )
    args = parser.parse_args(argv)

    # 0. Resilient checkpoint/restore (optional). Fails fast (before model load)
    #    if --experiment-branch is set but PAT/remote setup is broken.
    ckpt_config = _maybe_build_checkpoint_config(args)
    if ckpt_config is not None:
        from phi3geom.checkpointing import restore_from_branch

        result = restore_from_branch(ckpt_config)
        if result["branch_existed"]:
            print(
                f"[pilot] restored {result['events_restored']} events from "
                f"branch {args.experiment_branch}"
            )
        else:
            print(
                f"[pilot] fresh experiment branch {args.experiment_branch} "
                f"(no prior checkpoint on remote)"
            )

    # 1. Read the pinned model revision SHA.
    pin = read_pin(args.dataset_dir / "pinned_revision.json")
    model_id = pin["model_id"]
    model_revision_sha = pin["model_revision_sha"]
    print(f"[pilot] Using {model_id} @ {model_revision_sha[:8]}")

    # 2. Generate candidate events.
    split_seed = seed_for_split("v1")
    rng = random.Random(split_seed)
    if args.corpus == "synthetic":
        candidates = _generate_candidate_events(
            n_per_bin=args.n_per_bin, rng=rng,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            adversariality=args.adversariality,
            n_adversarial=args.n_adversarial,
        )
        print(
            f"[pilot] Generated {len(candidates)} candidate events from synthetic "
            f"corpus (adversariality={args.adversariality}, n={args.n_adversarial})"
        )
    elif args.corpus == "hotpotqa":
        from phi3geom.dataset.hotpotqa import load_hotpotqa_events

        n_total = args.n_per_bin * len(BIN_IDS)
        candidates = load_hotpotqa_events(
            n=n_total, rng=rng,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            split=args.hotpotqa_split,
        )
        print(
            f"[pilot] Loaded {len(candidates)} HotpotQA candidates from "
            f"split={args.hotpotqa_split} (bin assigned post-hoc from measured distance)"
        )
    else:  # pragma: no cover — argparse choices forbid this
        raise ValueError(f"unknown --corpus value: {args.corpus!r}")

    # 3. Load Phi-3 model + tokenizer.
    print("[pilot] Loading Phi-3-mini-128k-instruct (~8 GB GPU memory at fp16)...")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=model_revision_sha)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=model_revision_sha,
        torch_dtype=torch.float16, device_map="auto",
        attn_implementation="eager",  # needed for output_attentions=True
    )
    model.eval()

    # 4. Forward-pass + classify each candidate.
    t0 = time.monotonic()
    # We need a manifest SHA to seed cache headers — but the manifest is
    # finalized at the END of the run. Use a placeholder and re-key at the
    # end via a manifest re-write.
    placeholder_sha = "0" * 64
    code_commit_sha = _git_commit_sha()
    labeled: list[DocQAEvent] = []
    resumed = 0
    pending_event_ids: list[str] = []  # since-last-checkpoint buffer
    n_extracted_this_run = 0  # for per-event-time + ETA (resumes are instant; don't count)
    t_loop_start = time.monotonic()
    # For per-checkpoint batch-rate reporting (rolling window):
    t_last_checkpoint = t_loop_start
    n_extracted_at_last_checkpoint = 0
    for i, event in enumerate(candidates):
        cached = try_load_cached_event(event.event_id, cache_root=args.cache_root)
        progress = f"[pilot] {i + 1}/{len(candidates)} (bin {event.bin_id})"
        if n_extracted_this_run >= 3:
            elapsed_s = time.monotonic() - t_loop_start
            sec_per_ev = elapsed_s / n_extracted_this_run
            remaining_ev = len(candidates) - (i + 1)
            eta = datetime.datetime.utcnow() + datetime.timedelta(seconds=remaining_ev * sec_per_ev)
            progress += f"  [avg {sec_per_ev:.0f}s/ev, ETA {eta.strftime('%m-%d %H:%M')} UTC]"
        if cached is not None:
            print(f"{progress} RESUMED from cache", flush=True)
            labeled.append(cached)
            resumed += 1
        else:
            print(f"{progress} ...", flush=True)
            try:
                result = run_event_extraction(
                    event, model, tokenizer,
                    k_attn=args.k_attn,
                    manifest_sha256=placeholder_sha,
                    code_commit_sha=code_commit_sha,
                    cache_root=args.cache_root,
                    compute_ricci=args.with_ricci,
                )
            except RuntimeError as exc:
                print(
                    f"[pilot] event {event.event_id[:8]} skipped: {exc}",
                    file=sys.stderr,
                )
                continue
            labeled.append(result.event)
            n_extracted_this_run += 1
        pending_event_ids.append(event.event_id)

        # Periodic checkpoint (only if --experiment-branch is set).
        if (
            ckpt_config is not None
            and len(pending_event_ids) >= args.checkpoint_every
        ):
            # Batch-rate summary: shows whether speed is drifting over the
            # course of the run (rolling-window vs cumulative). Printed every
            # checkpoint so the user can read predicted finish-time from the
            # log without doing arithmetic.
            now = time.monotonic()
            total_elapsed = now - t_loop_start
            batch_elapsed = now - t_last_checkpoint
            batch_n = n_extracted_this_run - n_extracted_at_last_checkpoint
            remaining_ev = len(candidates) - (i + 1)
            print("[ckpt-status] " + "=" * 56, flush=True)
            print(
                f"[ckpt-status] {i + 1}/{len(candidates)} processed | "
                f"resumed={resumed} | extracted-this-run={n_extracted_this_run}",
                flush=True,
            )
            print(
                f"[ckpt-status] wall time:  {_fmt_dur(total_elapsed)}  | "
                f"batch time: {_fmt_dur(batch_elapsed)} ({batch_n} extractions)",
                flush=True,
            )
            if batch_n > 0 and n_extracted_this_run > 0:
                batch_rate = batch_elapsed / batch_n
                cum_rate = total_elapsed / n_extracted_this_run
                eta_batch = datetime.datetime.utcnow() + datetime.timedelta(
                    seconds=remaining_ev * batch_rate
                )
                eta_cum = datetime.datetime.utcnow() + datetime.timedelta(
                    seconds=remaining_ev * cum_rate
                )
                print(
                    f"[ckpt-status] batch rate: {batch_rate:>5.0f}s/ev    | "
                    f"cum rate:   {cum_rate:>5.0f}s/ev",
                    flush=True,
                )
                print(
                    f"[ckpt-status] ETA (batch): {eta_batch.strftime('%Y-%m-%d %H:%M UTC')} | "
                    f"ETA (cum):  {eta_cum.strftime('%Y-%m-%d %H:%M UTC')}",
                    flush=True,
                )
            print("[ckpt-status] " + "=" * 56, flush=True)

            _do_checkpoint(
                ckpt_config,
                event_ids=pending_event_ids,
                processed=i + 1,
                total=len(candidates),
                resumed=resumed,
                log_path=args.log_path,
                reports_dir=args.reports_dir,
            )
            pending_event_ids = []
            t_last_checkpoint = time.monotonic()
            n_extracted_at_last_checkpoint = n_extracted_this_run

    elapsed = time.monotonic() - t0
    if resumed > 0:
        print(
            f"[pilot] resume summary: {resumed}/{len(candidates)} events loaded from cache, "
            f"{len(candidates) - resumed} ran extraction"
        )

    # 5. CEM-match per bin to 50 fail + 50 ctrl.
    matched_events: list[DocQAEvent] = []
    strata_by_bin: dict[BinId, list[CEMStratum]] = {}
    for bin_id in BIN_IDS:
        bin_pool = [e for e in labeled if e.bin_id == bin_id]
        try:
            matched, strata = cem_match(
                bin_pool, bin_id=bin_id,
                target_per_class=args.target_per_class,
                rng=random.Random(seed_for_match(bin_id)),
            )
            matched_events.extend(matched)
            strata_by_bin[bin_id] = strata
        except MatchingFailedError as exc:
            print(f"[pilot] {exc}", file=sys.stderr)
            strata_by_bin[bin_id] = []

    # 5b. Pre-fit dataset sanity check. The 2026-06-04 run crashed here with
    #     n_samples=0 because Phi-3's 0.25% fail rate left CEM with ~4 matched
    #     events — wasted ~62 GPU-hours of extraction. Write a clear diagnostic
    #     and exit cleanly instead.
    n_fails_matched = sum(1 for e in matched_events if e.is_fail)
    n_controls_matched = len(matched_events) - n_fails_matched
    n_min_per_class = 10  # train_test_split with stratify=True needs both classes
    if min(n_fails_matched, n_controls_matched) < n_min_per_class:
        n_fails_all = sum(1 for e in labeled if e.is_fail)
        diag = {
            "n_candidates": len(candidates),
            "n_extracted_successfully": len(labeled),
            "n_matched": len(matched_events),
            "n_fails_matched": n_fails_matched,
            "n_controls_matched": n_controls_matched,
            "n_fails_in_full_extraction": n_fails_all,
            "n_controls_in_full_extraction": len(labeled) - n_fails_all,
            "fail_rate_full": n_fails_all / max(len(labeled), 1),
            "n_min_per_class_required": n_min_per_class,
            "matched_per_bin": {
                b: sum(1 for e in matched_events if e.bin_id == b) for b in BIN_IDS
            },
            "corpus": args.corpus,
            "adversariality": args.adversariality,
            "diagnosis": (
                "Failure rate too imbalanced for CEM matching. "
                "If fail_rate_full is near 0, the corpus is too easy "
                "(try --corpus hotpotqa or stronger --adversariality). "
                "If near 1, the corpus is too hard or the gold answers / EM "
                "normalization are mismatched."
            ),
        }
        args.reports_dir.mkdir(parents=True, exist_ok=True)
        diag_path = args.reports_dir / "dataset_diagnostic.json"
        diag_path.write_text(json.dumps(diag, indent=2, sort_keys=True))
        print(
            f"[pilot] ABORT: insufficient matched events "
            f"(fails={n_fails_matched}, controls={n_controls_matched}; "
            f"need ≥{n_min_per_class} of each). "
            f"See {diag_path} for full breakdown.",
            file=sys.stderr,
        )
        if ckpt_config is not None:
            _do_checkpoint(
                ckpt_config,
                event_ids=[e.event_id for e in labeled],
                processed=len(candidates),
                total=len(candidates),
                resumed=resumed,
                log_path=args.log_path,
                reports_dir=args.reports_dir,
                message=(
                    f"abort: dataset diagnostic "
                    f"(fails={n_fails_matched}, controls={n_controls_matched})"
                ),
            )
        return 2

    # 6. Pool ALL matched events into one distance-blind fit (Principle III,
    #    constitution v2.0.0). The detector never sees the bin or distance.
    import numpy as np
    features, labels = _build_feature_matrix(
        matched_events, cache_root=args.cache_root,
        expected_manifest_sha256=placeholder_sha,
    )
    distances = np.array([e.evidence_distance_tokens for e in matched_events])
    doc_lengths = np.array([len(e.document.split()) for e in matched_events])
    detector_fit = fit_pooled_detector(
        features, labels,
        feature_names=FEATURE_NAMES,
        random_state=seed_for_analysis("pooled_detector"),
    )
    print(
        f"[pilot] POOLED AUROC = {detector_fit.auroc:.3f} "
        f"(95% CI [{detector_fit.auroc_ci_lower:.3f}, "
        f"{detector_fit.auroc_ci_upper:.3f}]) "
        f"beats_chance={detector_fit.beats_chance} "
        f"on {len(matched_events)} pooled events"
    )

    # 7. Write the dataset manifest with real SHA.
    header = ManifestHeader(
        schema_version="1.0.0",
        manifest_sha256="0" * 64,  # filled by write_manifest
        events_sha256="0" * 64,
        code_commit_sha=code_commit_sha,
        model_revision_sha=model_revision_sha,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        generation_config_sha256=GENERATION_CONFIG_SHA256,
        k_grass=8,
        k_attn=args.k_attn,
        lookback_window_length=256,
        feature_layout=FEATURE_NAMES,
        forman_ricci_convention="nan_with_median_imputation_and_indicator",
        adversariality_policy_per_bin={b: args.adversariality for b in BIN_IDS},
        split_seed=split_seed,
        matching_seed_per_bin={b: seed_for_match(b) for b in BIN_IDS},
        constitution_version="1.0.0",
        spec_version="001",
        write_timestamp_utc=_now_iso(),
    )
    final_header = write_manifest(matched_events, header, args.dataset_dir)
    print(f"[pilot] manifest SHA = {final_header.manifest_sha256[:8]}")

    # 8. Write the pilot reports (pooled headline + diagnostics + ops).
    paths = write_pilot_summary(
        detector_fit=detector_fit,
        feature_matrix=features,
        labels=labels,
        distances=distances,
        doc_lengths=doc_lengths,
        strata_by_bin=strata_by_bin,
        wall_time_sec=elapsed,
        gpu_hours_estimate=elapsed / 3600.0,
        n_events=len(matched_events),
        matched_events=matched_events,
        random_state=seed_for_analysis("confound_audit"),
        out_dir=args.reports_dir,
    )
    for name, p in paths.items():
        print(f"[pilot] {name} → {p}")

    print(
        f"[pilot] done in {elapsed / 3600.0:.2f} GPU-hours "
        f"({elapsed / 60.0:.1f} min)."
    )

    # 9. Final checkpoint: stage everything (including the reports just written).
    if ckpt_config is not None:
        _do_checkpoint(
            ckpt_config,
            event_ids=[e.event_id for e in matched_events],
            processed=len(candidates),
            total=len(candidates),
            resumed=resumed,
            log_path=args.log_path,
            reports_dir=args.reports_dir,
            message=(
                f"final: {len(matched_events)} matched, "
                f"pooled AUROC={detector_fit.auroc:.3f} "
                f"(CI [{detector_fit.auroc_ci_lower:.3f}, "
                f"{detector_fit.auroc_ci_upper:.3f}])"
            ),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
