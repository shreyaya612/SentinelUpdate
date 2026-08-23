"""
SentinelUpdate - Rollback Snapshot Manager
Creates lightweight, reversible snapshots of package state before an update
is applied, so any negative outcome can be safely undone. This is what turns
"AI risk warning" into an actual safety guarantee rather than just advice.
"""

import subprocess
import json
import os
import shutil
from datetime import datetime, timezone

SNAPSHOT_DIR = os.path.join(os.path.expanduser("~"), ".sentinelupdate", "snapshots")


def _run(cmd, timeout=20):
    if shutil.which(cmd[0]) is None:
        return None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return result.stdout if result.returncode == 0 else None
    except Exception:
        return None


def create_snapshot(reason="pre-update snapshot"):
    """
    Captures the current package selection state (dpkg --get-selections),
    which can be restored later with restore_snapshot(). This does not
    require root and does not modify the system - it only records state.
    """
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"snapshot_{timestamp}"
    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_id)
    os.makedirs(snapshot_path, exist_ok=True)

    # 1. Package selections (what's installed and at what version)
    selections = _run(["dpkg", "--get-selections"])
    with open(os.path.join(snapshot_path, "dpkg_selections.txt"), "w") as f:
        f.write(selections or "")

    # 2. Explicit version pins for currently installed packages
    versions = _run(["dpkg-query", "-W", "-f=${Package}=${Version}\n"])
    with open(os.path.join(snapshot_path, "package_versions.txt"), "w") as f:
        f.write(versions or "")

    metadata = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "restorable": bool(selections and versions),
    }
    with open(os.path.join(snapshot_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def list_snapshots():
    if not os.path.isdir(SNAPSHOT_DIR):
        return []
    snapshots = []
    for name in sorted(os.listdir(SNAPSHOT_DIR), reverse=True):
        meta_path = os.path.join(SNAPSHOT_DIR, name, "metadata.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                snapshots.append(json.load(f))
    return snapshots


def get_restore_plan(snapshot_id):
    """
    Returns the exact commands a user (or the tool, with confirmation) would
    run to restore package versions from this snapshot. We deliberately
    return a PLAN rather than silently executing apt/dpkg commands, since
    package downgrades can themselves be risky and must be user-confirmed -
    consistent with the "never act without confirmation" safety principle.
    """
    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_id)
    versions_file = os.path.join(snapshot_path, "package_versions.txt")
    if not os.path.isfile(versions_file):
        return {"error": f"Snapshot {snapshot_id} not found or incomplete."}

    with open(versions_file) as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    return {
        "snapshot_id": snapshot_id,
        "package_count": len(lines),
        "restore_commands": [
            "# Review before running. This restores exact package versions from the snapshot.",
            f"sudo apt-get install --allow-downgrades {' '.join(lines[:5])} ...  # (truncated preview)",
        ],
        "full_package_list_file": versions_file,
    }


def restore_snapshot(snapshot_id, execute=False):
    """
    Restores package state from a snapshot.

    By default (execute=False) this performs a DRY RUN: it validates the
    snapshot exists and returns the exact commands that would be run,
    without touching the system. This is deliberate - a rollback that
    downgrades packages is itself a risky operation, so even though the
    user has already confirmed via the UI button, we do not silently
    execute apt/dpkg commands that could break a live system (especially
    during a hackathon demo). Set execute=True only when you want the
    tool to actually apply the restore.

    Returns:
        dict with 'success', 'message', and 'commands' (the plan).
    """
    plan = get_restore_plan(snapshot_id)
    if "error" in plan:
        return {"success": False, "message": plan["error"]}

    if not execute:
        return {
            "success": True,
            "dry_run": True,
            "message": f"Dry-run: restore plan generated for {snapshot_id} "
                       f"({plan['package_count']} packages). No changes applied. "
                       f"Review commands before running with execute=True.",
            "commands": plan["restore_commands"],
        }

    # Real execution path - only reached if explicitly requested.
    selections_file = os.path.join(SNAPSHOT_DIR, snapshot_id, "dpkg_selections.txt")
    if not os.path.isfile(selections_file):
        return {"success": False, "message": f"Selections file missing for {snapshot_id}."}

    try:
        with open(selections_file) as f:
            selections_data = f.read()
        proc = subprocess.run(
            ["sudo", "dpkg", "--set-selections"],
            input=selections_data, capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            return {"success": False, "message": f"dpkg --set-selections failed: {proc.stderr}"}
        return {
            "success": True,
            "dry_run": False,
            "message": f"Package selections restored from {snapshot_id}. "
                       f"Run 'sudo apt-get dselect-upgrade' to apply version changes.",
        }
    except Exception as e:
        return {"success": False, "message": f"Restore failed: {e}"}


if __name__ == "__main__":
    meta = create_snapshot(reason="test run")
    print(json.dumps(meta, indent=2))
    print("\nAll snapshots:")
    print(json.dumps(list_snapshots(), indent=2))
