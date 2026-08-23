"""
SentinelUpdate - CLI Entry Point
Run a full scan -> risk score -> AI explanation pipeline from the terminal,
without needing the web dashboard. Useful for scripting / cron / CI use.

Usage:
    python3 main.py scan [--demo] [--json]
    python3 main.py snapshot [--reason "text"]
    python3 main.py snapshots
"""

from dotenv import load_dotenv
load_dotenv()  # loads GEMINI_API_KEY from a local .env file if present

import argparse
import json
import sys

from scanner.system_scanner import scan_system, get_loaded_modules
from risk_engine.risk_scorer import score_all_updates
from ai_layer.explainer import explain_all
from rollback.snapshot import create_snapshot, list_snapshots

DEMO_UPDATES = [
    {"package": "linux-image-6.8.0-49-generic", "old_version": "6.8.0-48.48", "new_version": "6.8.0-49.49"},
    {"package": "nvidia-driver-535", "old_version": "535.104.05", "new_version": "535.183.01"},
    {"package": "curl", "old_version": "8.5.0-2ubuntu10.1", "new_version": "8.5.0-2ubuntu10.2"},
]
DEMO_LOADED_MODULES = ["nvidia", "nvidia_uvm", "nvidia_drm", "ext4", "usbcore"]

# ANSI color escape codes for terminal formatting
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_BOLD = "\033[1m"


def get_risk_color(level: str) -> str:
    """Returns ANSI color based on risk severity."""
    lvl = str(level).upper()
    if "HIGH" in lvl:
        return COLOR_RED
    elif "MEDIUM" in lvl:
        return COLOR_YELLOW
    elif "LOW" in lvl:
        return COLOR_GREEN
    return COLOR_RESET


def cmd_scan(args):
    if args.demo:
        pending, modules = DEMO_UPDATES, DEMO_LOADED_MODULES
    else:
        snap = scan_system()
        pending, modules = snap.get("pending_updates", []), get_loaded_modules()
        if not pending:
            print("[info] no live pending updates found — falling back to demo dataset\n", file=sys.stderr)
            pending, modules = DEMO_UPDATES, DEMO_LOADED_MODULES

    scored = score_all_updates(pending, loaded_modules=modules)

    # Guard against API failure during live demos
    try:
        results = explain_all(scored)
    except Exception as e:
        print(f"[warning] AI explanation failed ({e}). Displaying rule-based score only.\n", file=sys.stderr)
        results = scored

    print("=" * 70)
    for r in results:
        risk_level = r.get("level", "UNKNOWN")
        color = get_risk_color(risk_level)

        print(f"{COLOR_BOLD}{r.get('package')} ({r.get('old_version')} -> {r.get('new_version')}){COLOR_RESET}")
        print(f"RISK: {color}{COLOR_BOLD}{risk_level}{COLOR_RESET} (score: {r.get('score', 0)}/100)")

        signals = r.get("signals", [])
        if signals:
            print("Signals:")
            for s in signals:
                print(f"  - {s}")

        explanation = r.get("explanation")
        if explanation:
            print(f"\n{explanation}")

        action = r.get("recommended_action")
        if action:
            print(f"-> {COLOR_BOLD}{action}{COLOR_RESET}")

        print("-" * 70)

    if args.json:
        print(json.dumps(results, indent=2))


def cmd_snapshot(args):
    meta = create_snapshot(reason=args.reason)
    print(json.dumps(meta, indent=2))


def cmd_snapshots(args):
    print(json.dumps(list_snapshots(), indent=2))


def main():
    parser = argparse.ArgumentParser(description="SentinelUpdate - AI-powered pre-update risk advisor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan pending updates and assess risk")
    p_scan.add_argument("--demo", action="store_true", help="Use demo dataset instead of live system")
    p_scan.add_argument("--json", action="store_true", help="Also print raw JSON output")
    p_scan.set_defaults(func=cmd_scan)

    p_snap = sub.add_parser("snapshot", help="Create a rollback snapshot")
    p_snap.add_argument("--reason", default="manual CLI snapshot")
    p_snap.set_defaults(func=cmd_snapshot)

    p_list = sub.add_parser("snapshots", help="List existing snapshots")
    p_list.set_defaults(func=cmd_snapshots)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
