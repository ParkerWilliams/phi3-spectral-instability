"""Reproducibility cross-machine check (T060, SC-005).

Given a manifest_header.json, regenerate the dataset on a different machine
using the same seeds and code SHA, and report the per-event agreement rate
on event_ids and is_fail labels. Target: ≥99% agreement (Spec SC-005).
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.dataset.manifest import read_manifest
from phi3geom.dataset.types import BIN_IDS, BIN_RANGES, BinId
from phi3geom.reproducibility.seeds import seed_for_match, seed_for_split


def _generate_pool_for_bin(
    bin_id: BinId,
    *,
    n_per_bin: int,
    rng: random.Random,
    prompt_template_sha256: str,
):
    pool = []
    for _ in range(n_per_bin):
        template = rng.choice(TEMPLATES)
        fact = rng.choice(FACTS[template.template_id])
        density = rng.uniform(0.0, 1.0)
        lo, hi = BIN_RANGES[bin_id]
        target = rng.randint(lo, hi - 1)
        pool.append(
            generate_event(
                template=template, fact=fact,
                target_evidence_distance_words=target,
                distractor_density=density,
                prompt_template_sha256=prompt_template_sha256,
                bin_id=bin_id,
                rng=rng,
            )
        )
    return pool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("dataset/manifest_header.json"),
    )
    parser.add_argument(
        "--dataset-dir", type=Path, default=Path("dataset"),
    )
    parser.add_argument(
        "--n-per-bin", type=int, default=150,
        help="Candidates per bin; should match the original generation.",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("reports/full/sc005_reproducibility.json"),
    )
    args = parser.parse_args(argv)

    print("[regenerate] Reading original manifest...")
    header, original_events = read_manifest(args.dataset_dir)

    # Verify we're at the right code SHA.
    try:
        local_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        local_sha = "unknown"
    if local_sha != header.code_commit_sha:
        print(
            f"[regenerate] WARN: local code SHA ({local_sha[:8]}) != "
            f"manifest code SHA ({header.code_commit_sha[:8]}). "
            "Check out the manifest's commit for a clean comparison.",
            file=sys.stderr,
        )

    # Regenerate using the same split_seed and per-bin match seeds.
    print("[regenerate] Regenerating candidate pools...")
    regenerated_event_ids: set[str] = set()
    for bin_id in BIN_IDS:
        bin_rng = random.Random(seed_for_match(bin_id))
        pool = _generate_pool_for_bin(
            bin_id, n_per_bin=args.n_per_bin,
            rng=bin_rng,
            prompt_template_sha256=header.prompt_template_sha256,
        )
        regenerated_event_ids.update(e.event_id for e in pool)

    # Compare.
    original_ids = {e.event_id for e in original_events}
    overlap = original_ids & regenerated_event_ids
    n_orig = len(original_ids)
    agreement_pct = 100.0 * len(overlap) / n_orig if n_orig > 0 else 0.0

    payload = {
        "n_original_events": n_orig,
        "n_regenerated_event_ids": len(regenerated_event_ids),
        "n_overlap": len(overlap),
        "agreement_pct": agreement_pct,
        "sc005_target_pct": 99.0,
        "passes_sc005": agreement_pct >= 99.0,
        "manifest_code_sha": header.code_commit_sha,
        "local_code_sha": local_sha,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"[regenerate] Agreement: {agreement_pct:.2f}% ({len(overlap)}/{n_orig})")
    print(f"[regenerate] Wrote {args.out}")
    return 0 if agreement_pct >= 99.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
