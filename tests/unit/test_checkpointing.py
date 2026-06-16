"""Checkpoint reduced cache + log to a git experiment branch.

Pushes the small reduced data (F_summary + event.json) that the v2.0.0
pooled detector actually reads — not the big F.npy/D.npy tensors which
are deferred-feature territory. See ``phi3geom.checkpointing`` docstring.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from phi3geom.checkpointing import (
    ARTIFACT_DIR_NAME,
    CheckpointConfig,
    branch_exists_on_remote,
    checkpoint,
    git_checkpoint,
    mirror_log,
    restore_artifacts_to_cache,
    restore_from_branch,
    stage_event_summary,
    write_progress,
)

# ---------------------------------------------------------------------------
# Per-event staging
# ---------------------------------------------------------------------------

EVENT_ID = "abcdef" + "0" * 58  # 64 hex chars


def _seed_cache(cache_root: Path, event_id: str, names: tuple[str, ...]) -> Path:
    d = cache_root / event_id[:2] / event_id
    d.mkdir(parents=True)
    for n in names:
        (d / n).write_bytes(b"dummy:" + n.encode())
    return d


def test_stage_copies_all_three_summary_files(tmp_path):
    cache_root = tmp_path / "cache"
    art = tmp_path / ARTIFACT_DIR_NAME
    _seed_cache(cache_root, EVENT_ID, ("F_summary.npy", "F_summary.header.json", "event.json"))
    copied = stage_event_summary(EVENT_ID, cache_root=cache_root, artifact_root=art)
    dst = art / "cache" / EVENT_ID[:2] / EVENT_ID
    assert sorted(p.name for p in copied) == [
        "F_summary.header.json", "F_summary.npy", "event.json",
    ]
    assert (dst / "F_summary.npy").read_bytes() == b"dummy:F_summary.npy"


def test_stage_silently_skips_missing_files(tmp_path):
    cache_root = tmp_path / "cache"
    art = tmp_path / ARTIFACT_DIR_NAME
    _seed_cache(cache_root, EVENT_ID, ("F_summary.npy",))  # no event.json
    copied = stage_event_summary(EVENT_ID, cache_root=cache_root, artifact_root=art)
    assert [p.name for p in copied] == ["F_summary.npy"]
    assert not (art / "cache" / EVENT_ID[:2] / EVENT_ID / "event.json").exists()


def test_write_progress_roundtrip(tmp_path):
    art = tmp_path / ARTIFACT_DIR_NAME
    payload = {"events_done": 175, "resumed": 50, "skipped": 7, "current_bin": "B2"}
    path = write_progress(payload, artifact_root=art)
    assert path == art / "progress.json"
    assert json.loads(path.read_text()) == payload


def test_mirror_log_copies_under_log_subdir(tmp_path):
    art = tmp_path / ARTIFACT_DIR_NAME
    src_log = tmp_path / "reports" / "pilot_run.log"
    src_log.parent.mkdir()
    src_log.write_text("[pilot] 1/900 (bin B1) ...\n")
    dst = mirror_log(src_log, artifact_root=art)
    assert dst == art / "log" / "pilot_run.log"
    assert dst.read_text() == "[pilot] 1/900 (bin B1) ...\n"


def test_mirror_log_returns_none_when_missing(tmp_path):
    assert mirror_log(tmp_path / "nope.log", artifact_root=tmp_path / "art") is None


# ---------------------------------------------------------------------------
# CheckpointConfig — token injection
# ---------------------------------------------------------------------------

def _toy_config(tmp_path, branch="experiment/test", token="ghp_TESTTOKEN") -> CheckpointConfig:
    return CheckpointConfig(
        branch=branch,
        token=token,
        remote_url="https://github.com/owner/repo.git",
        cache_root=tmp_path / "cache",
        artifact_root=tmp_path / ARTIFACT_DIR_NAME,
        repo_root=tmp_path / "work",
    )


def test_push_url_injects_token(tmp_path):
    cfg = _toy_config(tmp_path)
    assert cfg.push_url == "https://x-access-token:ghp_TESTTOKEN@github.com/owner/repo.git"


def test_push_url_rejects_non_https(tmp_path):
    cfg = CheckpointConfig(
        branch="b", token="t", remote_url="git@github.com:owner/repo.git",
        cache_root=tmp_path, artifact_root=tmp_path, repo_root=tmp_path,
    )
    with pytest.raises(ValueError, match="https"):
        _ = cfg.push_url


# ---------------------------------------------------------------------------
# git_checkpoint — real git, local bare remote stand-in
# ---------------------------------------------------------------------------

def _init_repos(tmp_path: Path) -> tuple[Path, str]:
    """Create a working repo + bare remote. Returns (work_dir, file:// remote URL)."""
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    work.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    for k, v in (("user.email", "test@example.com"), ("user.name", "Test")):
        subprocess.run(["git", "-C", str(work), "config", k, v], check=True)
    (work / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(work), "commit", "-m", "init"], check=True, capture_output=True
    )
    return work, f"file://{remote}"


def test_git_checkpoint_creates_and_pushes_commit(tmp_path):
    work, remote = _init_repos(tmp_path)
    art = work / ARTIFACT_DIR_NAME
    art.mkdir()
    (art / "progress.json").write_text("{}")

    pushed = git_checkpoint(
        message="ckpt: 25 events",
        repo_root=work,
        branch="experiment/test",
        push_url=remote,
        paths_to_add=[art],
    )
    assert pushed is True
    log = subprocess.run(
        ["git", "-C", str(tmp_path / "remote.git"), "log", "--oneline", "experiment/test"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "ckpt: 25 events" in log


def test_git_checkpoint_returns_false_when_nothing_new(tmp_path):
    work, remote = _init_repos(tmp_path)
    pushed = git_checkpoint(
        message="empty", repo_root=work, branch="experiment/test",
        push_url=remote, paths_to_add=[],
    )
    assert pushed is False


def test_git_checkpoint_commits_artifacts_despite_hostile_gitignore(tmp_path):
    """Regression: the real repo's unanchored ``cache/`` and ``reports/``
    .gitignore patterns matched the COPIES under ``experiment_artifacts/`` and
    silently dropped the F_summary tensors + report JSONs from every checkpoint
    (the 2026-06-09 and 2026-06-14 pilots both lost their data this way). The
    checkpoint MUST commit them regardless of the working tree's .gitignore."""
    work, remote = _init_repos(tmp_path)
    (work / ".gitignore").write_text("cache/\nreports/\n")  # unanchored = hostile
    subprocess.run(["git", "-C", str(work), "add", ".gitignore"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "commit", "-m", "gitignore"], check=True, capture_output=True)

    art = work / ARTIFACT_DIR_NAME
    ev_dir = art / "cache" / "aa" / "ev"
    ev_dir.mkdir(parents=True)
    (ev_dir / "F_summary.npy").write_bytes(b"tensor-data")
    (art / "reports").mkdir(parents=True)
    (art / "reports" / "pooled_auroc.json").write_text('{"auroc": 0.5}')

    pushed = git_checkpoint(
        message="ckpt: with artifacts", repo_root=work,
        branch="experiment/test", push_url=remote, paths_to_add=[art],
    )
    assert pushed is True
    tree = subprocess.run(
        ["git", "-C", str(tmp_path / "remote.git"), "ls-tree", "-r",
         "--name-only", "experiment/test"],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "experiment_artifacts/cache/aa/ev/F_summary.npy" in tree
    assert "experiment_artifacts/reports/pooled_auroc.json" in tree


# ---------------------------------------------------------------------------
# checkpoint() orchestrator
# ---------------------------------------------------------------------------

def test_checkpoint_orchestrator_stages_and_pushes(tmp_path):
    work, remote = _init_repos(tmp_path)
    cache_root = tmp_path / "cache"
    _seed_cache(cache_root, EVENT_ID, ("F_summary.npy", "F_summary.header.json", "event.json"))
    log_path = tmp_path / "pilot_run.log"
    log_path.write_text("first checkpoint\n")
    reports_dir = tmp_path / "reports_partial"
    reports_dir.mkdir()
    (reports_dir / "pooled_auroc.json").write_text('{"auroc": 0.7}')

    cfg = CheckpointConfig(
        branch="experiment/test",
        token="ignored-for-file-url",
        remote_url="https://github.com/owner/repo.git",  # not actually used; we override push_url path
        cache_root=cache_root,
        artifact_root=work / ARTIFACT_DIR_NAME,
        repo_root=work,
    )
    # use the bare-remote file URL directly via git_checkpoint args; bypass push_url
    # for this test by calling the orchestrator with a monkey-patched url
    # via an indirect: we just trust git_checkpoint() (tested above) and assert
    # the orchestrator wires staging properly.
    from phi3geom import checkpointing as ckpt
    pushed = ckpt.checkpoint(
        cfg,
        event_ids=[EVENT_ID],
        progress={"events_done": 1},
        log_path=log_path,
        extra_report_dir=reports_dir,
        message="ckpt: 1 event",
        push_url_override=remote,  # test-only override; default uses cfg.push_url
    )
    assert pushed is True

    art = work / ARTIFACT_DIR_NAME
    assert (art / "cache" / EVENT_ID[:2] / EVENT_ID / "F_summary.npy").is_file()
    assert (art / "log" / "pilot_run.log").read_text() == "first checkpoint\n"
    assert (art / "reports" / "pooled_auroc.json").read_text() == '{"auroc": 0.7}'
    assert json.loads((art / "progress.json").read_text()) == {"events_done": 1}


# ---------------------------------------------------------------------------
# Restore from an existing experiment branch
# ---------------------------------------------------------------------------

def test_branch_exists_on_remote_reports_true_for_pushed_branch(tmp_path):
    work, remote = _init_repos(tmp_path)
    subprocess.run(
        ["git", "-C", str(work), "push", remote, "main"],
        check=True, capture_output=True,
    )
    assert branch_exists_on_remote(remote, "main") is True


def test_branch_exists_on_remote_reports_false_for_missing(tmp_path):
    _, remote = _init_repos(tmp_path)
    assert branch_exists_on_remote(remote, "experiment/never-pushed") is False


def test_restore_artifacts_to_cache_copies_and_counts(tmp_path):
    art = tmp_path / ARTIFACT_DIR_NAME
    e1 = "aa" + "a" * 62
    e2 = "bb" + "b" * 62
    for eid in (e1, e2):
        d = art / "cache" / eid[:2] / eid
        d.mkdir(parents=True)
        (d / "F_summary.npy").write_bytes(b"sum:" + eid.encode())
        (d / "event.json").write_text("{}")
    cache = tmp_path / "cache"
    n = restore_artifacts_to_cache(artifact_root=art, cache_root=cache)
    assert n == 2
    assert (cache / e1[:2] / e1 / "F_summary.npy").read_bytes() == b"sum:" + e1.encode()
    assert (cache / e2[:2] / e2 / "event.json").read_text() == "{}"


def test_restore_artifacts_to_cache_no_op_when_artifact_dir_missing(tmp_path):
    n = restore_artifacts_to_cache(
        artifact_root=tmp_path / "nope", cache_root=tmp_path / "cache",
    )
    assert n == 0


def test_restore_from_branch_noop_when_branch_missing(tmp_path):
    work, remote = _init_repos(tmp_path)
    cfg = CheckpointConfig(
        branch="experiment/never-pushed",
        token="ignored",
        remote_url="https://github.com/owner/repo.git",
        cache_root=tmp_path / "cache",
        artifact_root=work / ARTIFACT_DIR_NAME,
        repo_root=work,
    )
    result = restore_from_branch(cfg, push_url_override=remote)
    assert result == {"branch_existed": False, "events_restored": 0}


def test_restore_from_branch_end_to_end(tmp_path):
    """A checkpoint pushed from one repo restores cleanly into a fresh one."""
    # 1. First "pod": init + checkpoint a single event to experiment/foo.
    work_a, remote = _init_repos(tmp_path)
    cache_a = tmp_path / "cache_a"
    _seed_cache(
        cache_a, EVENT_ID,
        ("F_summary.npy", "F_summary.header.json", "event.json"),
    )
    cfg_a = CheckpointConfig(
        branch="experiment/foo",
        token="ignored",
        remote_url="https://github.com/owner/repo.git",
        cache_root=cache_a,
        artifact_root=work_a / ARTIFACT_DIR_NAME,
        repo_root=work_a,
    )
    pushed = checkpoint(
        cfg_a, event_ids=[EVENT_ID], progress={"events_done": 1},
        log_path=None, extra_report_dir=None, message="ckpt",
        push_url_override=remote,
    )
    assert pushed is True

    # 2. Fresh "second pod": empty cache, fresh clone.
    work_b = tmp_path / "work_b"
    subprocess.run(
        ["git", "clone", remote, str(work_b)], check=True, capture_output=True
    )
    for k, v in (("user.email", "b@b"), ("user.name", "B")):
        subprocess.run(["git", "-C", str(work_b), "config", k, v], check=True)
    cache_b = tmp_path / "cache_b"  # empty
    cfg_b = CheckpointConfig(
        branch="experiment/foo",
        token="ignored",
        remote_url="https://github.com/owner/repo.git",
        cache_root=cache_b,
        artifact_root=work_b / ARTIFACT_DIR_NAME,
        repo_root=work_b,
    )
    result = restore_from_branch(cfg_b, push_url_override=remote)
    assert result["branch_existed"] is True
    assert result["events_restored"] == 1

    # 3. cache_b now has the restored summary + event.json (resume contract).
    assert (cache_b / EVENT_ID[:2] / EVENT_ID / "F_summary.npy").is_file()
    assert (cache_b / EVENT_ID[:2] / EVENT_ID / "event.json").is_file()

    # 4. work_b's HEAD is now on the experiment branch.
    head = subprocess.run(
        ["git", "-C", str(work_b), "rev-parse", "--abbrev-ref", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert head == "experiment/foo"
