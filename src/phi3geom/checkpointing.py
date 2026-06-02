"""Per-event checkpoint of reduced cache + log to a git experiment branch.

Architecture rationale
----------------------
The full cache (F.npy + D.npy + F_summary.npy) is ~30 MB/event ≈ 27 GB for
a full pilot — too big for git. But the **v2.0.0 pooled-detector path only
reads F_summary.npy** (~35 KB/event); F.npy and D.npy are needed only for
deferred per-position attribution and FDA β(ℓ) depth work. So we push the
reduced data (F_summary + event.json + small header) to an experiment
branch: ~36 KB/event × 900 ≈ ~32 MB total, which fits trivially in git.

After every N events the pilot calls :func:`checkpoint`, which:

1. Copies the reduced per-event files into ``experiment_artifacts/cache/``.
2. Mirrors the run log into ``experiment_artifacts/log/``.
3. Mirrors any partial reports JSON into ``experiment_artifacts/reports/``.
4. Writes ``experiment_artifacts/progress.json`` with stats.
5. ``git add experiment_artifacts/`` + commit + push to the experiment branch.

A fresh pod clones the experiment branch, copies ``experiment_artifacts/cache/``
back into ``cache/``, and the resume-from-cache logic in ``pilot_main``
(:func:`phi3geom.storage.cache.try_load_cached_event`) skips the events whose
F_summary + event.json are restored.

The push URL injects a fine-grained GitHub PAT — passed as a subprocess
argument only, never written into git config.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ARTIFACT_DIR_NAME = "experiment_artifacts"
SUMMARY_FILENAMES: tuple[str, ...] = (
    "F_summary.npy",
    "F_summary.header.json",
    "event.json",
)


@dataclass(frozen=True)
class CheckpointConfig:
    """Per-pod checkpoint setup; built once at startup, reused per checkpoint."""

    branch: str
    token: str
    remote_url: str  # https://github.com/owner/repo.git
    cache_root: Path
    artifact_root: Path  # typically repo_root / ARTIFACT_DIR_NAME
    repo_root: Path

    @property
    def push_url(self) -> str:
        """Token-injected URL for `git push`; passed as argv only, never stored."""
        if not self.remote_url.startswith("https://"):
            raise ValueError(
                f"remote_url must start with https:// for PAT auth; got {self.remote_url!r}"
            )
        return self.remote_url.replace(
            "https://", f"https://x-access-token:{self.token}@", 1
        )


def stage_event_summary(
    event_id: str,
    *,
    cache_root: Path,
    artifact_root: Path,
) -> list[Path]:
    """Copy F_summary + headers + event.json from ``cache/`` to ``artifact_root/cache/``.

    Mirrors the same ``<id_prefix>/<event_id>/`` layout so restore is a
    straight copy back. Missing source files are silently skipped — the
    resume contract checks file presence, not exhaustiveness.
    """
    src_dir = cache_root / event_id[:2] / event_id
    dst_dir = artifact_root / "cache" / event_id[:2] / event_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in SUMMARY_FILENAMES:
        src = src_dir / name
        if src.is_file():
            dst = dst_dir / name
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def write_progress(progress: dict, *, artifact_root: Path) -> Path:
    """Write a small ``progress.json`` (events done, skipped, resumed, rate, ...)."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    path = artifact_root / "progress.json"
    path.write_text(json.dumps(progress, indent=2, sort_keys=True))
    return path


def mirror_log(log_path: Path, *, artifact_root: Path) -> Path | None:
    """Copy a run log file into ``artifact_root/log/`` so it's part of the commit.

    Returns the destination path, or ``None`` if the source doesn't exist
    (the pilot is fine with a missing log — e.g. on the first checkpoint
    before nohup has flushed any output).
    """
    if not log_path.is_file():
        return None
    dst_dir = artifact_root / "log"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / log_path.name
    shutil.copy2(log_path, dst)
    return dst


def git_checkpoint(
    *,
    message: str,
    repo_root: Path,
    branch: str,
    push_url: str,
    paths_to_add: Iterable[Path],
) -> bool:
    """Stage paths, commit if anything changed, push HEAD to ``branch`` on remote.

    Returns:
        ``True`` if a commit was created and pushed; ``False`` if nothing
        new since the last checkpoint (idempotent calls are safe).

    Raises:
        subprocess.CalledProcessError: any git command failed. The caller
        decides whether to retry or abort the run.
    """
    add_args = ["git", "-C", str(repo_root), "add"] + [str(p) for p in paths_to_add]
    if len(add_args) > 4:  # any paths after the 'add' subcommand
        subprocess.run(add_args, check=True)

    staged = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not staged:
        return False

    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", message],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "push", push_url, f"HEAD:{branch}"],
        check=True,
    )
    return True


def branch_exists_on_remote(push_url: str, branch: str) -> bool:
    """Return ``True`` iff ``branch`` is published at ``push_url``.

    Cheap probe via ``git ls-remote --heads``; no fetch, no working-tree
    side effects. Used by :func:`restore_from_branch` to decide whether
    this is a first-pod or resume-pod startup.
    """
    result = subprocess.run(
        ["git", "ls-remote", "--heads", push_url, branch],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def fetch_and_checkout_branch(
    *, push_url: str, branch: str, repo_root: Path
) -> None:
    """Fetch ``branch`` from ``push_url`` and switch the local working tree to it.

    The local branch is created or hard-reset to match the remote tip (``-B``).
    Caller is responsible for a clean working tree — restore happens at
    startup, before extraction work begins.
    """
    fetch_ref = f"refs/remotes/checkpoint-restore/{branch}"
    subprocess.run(
        ["git", "-C", str(repo_root), "fetch", push_url, f"{branch}:{fetch_ref}"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "checkout", "-B", branch, fetch_ref],
        check=True,
        capture_output=True,
    )


def restore_artifacts_to_cache(
    *, artifact_root: Path, cache_root: Path
) -> int:
    """Copy ``artifact_root/cache/`` → ``cache_root/``. Returns events restored.

    Same per-event layout in both directions, so the resume-from-cache
    skip in ``pilot_main`` finds the restored summaries automatically.
    Existing files in ``cache_root`` are overwritten by same-named restored
    files; unrelated local cache entries are left untouched.
    """
    src = artifact_root / "cache"
    if not src.is_dir():
        return 0
    cache_root.mkdir(parents=True, exist_ok=True)
    n = sum(1 for _ in src.rglob("F_summary.npy"))
    shutil.copytree(src, cache_root, dirs_exist_ok=True)
    return n


def restore_from_branch(
    config: CheckpointConfig,
    *,
    push_url_override: str | None = None,
) -> dict:
    """One-call startup restore: fetch + checkout + populate cache.

    Returns ``{"branch_existed": bool, "events_restored": int}``. A
    first-pod run (no prior experiment branch on remote) returns
    ``{"branch_existed": False, "events_restored": 0}`` and leaves the
    working tree alone — the caller then runs extraction from scratch.
    """
    url = push_url_override if push_url_override is not None else config.push_url
    if not branch_exists_on_remote(url, config.branch):
        return {"branch_existed": False, "events_restored": 0}
    fetch_and_checkout_branch(
        push_url=url, branch=config.branch, repo_root=config.repo_root,
    )
    n = restore_artifacts_to_cache(
        artifact_root=config.artifact_root, cache_root=config.cache_root,
    )
    return {"branch_existed": True, "events_restored": n}


def checkpoint(
    config: CheckpointConfig,
    *,
    event_ids: Iterable[str],
    progress: dict,
    log_path: Path | None,
    extra_report_dir: Path | None,
    message: str,
    push_url_override: str | None = None,
) -> bool:
    """One-call checkpoint: stage everything, then ``git add`` + commit + push.

    Args:
        push_url_override: Test seam. Production callers leave this ``None``
            and the PAT-injected URL from ``config.push_url`` is used.

    Returns:
        ``True`` if a commit was pushed, ``False`` if nothing changed.
    """
    for event_id in event_ids:
        stage_event_summary(
            event_id, cache_root=config.cache_root, artifact_root=config.artifact_root
        )
    write_progress(progress, artifact_root=config.artifact_root)
    if log_path is not None:
        mirror_log(log_path, artifact_root=config.artifact_root)
    if extra_report_dir is not None and extra_report_dir.is_dir():
        dst_reports = config.artifact_root / "reports"
        dst_reports.mkdir(parents=True, exist_ok=True)
        for src in extra_report_dir.glob("*.json"):
            shutil.copy2(src, dst_reports / src.name)
    return git_checkpoint(
        message=message,
        repo_root=config.repo_root,
        branch=config.branch,
        push_url=push_url_override if push_url_override is not None else config.push_url,
        paths_to_add=[config.artifact_root],
    )
