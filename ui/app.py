from dotenv import load_dotenv
load_dotenv()  # loads GEMINI_API_KEY from a local .env file if present

import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from scanner.system_scanner import scan_system, get_system_context
from risk_engine.risk_scorer import score_all_updates
from ai_layer.explainer import explain_all, _AI_AVAILABLE as EXPLAINER_AI_AVAILABLE
from ai_layer.changelog_analyzer import enrich_with_changelog_analysis
from rollback.snapshot import create_snapshot, list_snapshots, restore_snapshot

app = Flask(__name__)

DEMO_UPDATES = [
    {"package": "linux-image-6.8.0-49-generic", "old_version": "6.8.0-48.48", "new_version": "6.8.0-49.49"},
    {"package": "nvidia-driver-535", "old_version": "535.104.05", "new_version": "535.183.01"},
    {"package": "curl", "old_version": "8.5.0-2ubuntu10.1", "new_version": "8.5.0-2ubuntu10.2"},
    {"package": "openssh-server", "old_version": "1:9.6p1-3ubuntu13.5", "new_version": "1:9.6p1-3ubuntu13.6"},
    {"package": "systemd", "old_version": "255.4-1ubuntu8.4", "new_version": "255.4-1ubuntu8.6"},
]
DEMO_LOADED_MODULES = ["nvidia", "nvidia_uvm", "nvidia_drm", "ext4", "usbcore"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan")
def api_scan():
    use_demo = request.args.get("demo", "true").lower() == "true"
    deep_analysis = request.args.get("deep", "false").lower() == "true"

    if use_demo:
        pending_updates = DEMO_UPDATES
        loaded_modules = DEMO_LOADED_MODULES
        source = "demo_dataset"
    else:
        snap = scan_system()
        pending_updates = snap.get("pending_updates", [])
        loaded_modules = snap.get("system_context", {}).get("loaded_modules", [])
        source = "live_system"
        if not pending_updates:
            pending_updates = DEMO_UPDATES
            loaded_modules = DEMO_LOADED_MODULES
            source = "demo_dataset_fallback (no live pending updates found)"

    scored = score_all_updates(pending_updates, loaded_modules=loaded_modules)
    scored.sort(key=lambda r: r["score"], reverse=True)

    if deep_analysis:
        scored = enrich_with_changelog_analysis(scored, max_packages=5)

    results = explain_all(scored)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    results.sort(key=lambda r: order.get(r.get("level", "LOW"), 3))

    return jsonify({
        "source": source,
        "scanned_at": datetime.datetime.now().strftime("%H:%M:%S"),
        "updates": results,
        "ai_available": EXPLAINER_AI_AVAILABLE,
        "deep_analysis_requested": deep_analysis,
        "summary": {
            "total": len(results),
            "high": sum(1 for r in results if r["level"] == "HIGH"),
            "medium": sum(1 for r in results if r["level"] == "MEDIUM"),
            "low": sum(1 for r in results if r["level"] == "LOW"),
        }
    })
@app.route("/api/status")
def api_status():
    """Lets the UI show a plain status badge instead of leaving it to guess
    whether AI features are actually active - silent fallbacks are exactly
    what an explainability-first tool should never hide from the user."""
    return jsonify({
        "ai_available": EXPLAINER_AI_AVAILABLE,
        "gemini_api_key_set": bool(os.getenv("GEMINI_API_KEY")),
    })

@app.route("/api/system")
def api_system():
    return jsonify(get_system_context())


@app.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    reason = "manual snapshot"
    if request.is_json:
        reason = request.json.get("reason", reason)
    meta = create_snapshot(reason=reason)
    return jsonify(meta)


@app.route("/api/snapshots")
def api_list_snapshots():
    return jsonify(list_snapshots())


@app.route("/api/restore", methods=["POST"])
def api_restore():
    if not request.is_json:
        return jsonify({"success": False, "message": "snapshot_id required"}), 400
    snapshot_id = request.json.get("snapshot_id")
    execute = request.json.get("execute", False)
    if not snapshot_id:
        return jsonify({"success": False, "message": "snapshot_id required"}), 400
    result = restore_snapshot(snapshot_id, execute=execute)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
