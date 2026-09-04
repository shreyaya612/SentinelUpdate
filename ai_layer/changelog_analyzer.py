"""
SentinelUpdate - Changelog Risk Analyzer (network + local + reference fallback)
Second, independent AI signal source. Reads a package's REAL changelog text
and asks Gemini to identify concrete risk indicators no version number could
reveal (breaking changes, deprecations, required reboots), with a bounded
score contribution and a citation.

fetch_changelog() tries three sources in order:
  1. LIVE (apt-get changelog, network) - gets the exact pending version's
     entry, most accurate.
  2. LOCAL (/usr/share/doc/<pkg>/changelog.Debian.gz, on-disk) - no network
     required at all, still real content (recent version history, CVE fixes).
  3. REFERENCE - curated realistic text for the curated DEMO_UPDATES
     packages only (fictional example versions like nvidia-driver-535 that
     aren't actually installed anywhere, so neither real strategy can find
     data for them). Only reached if both real strategies already failed.
This means the feature degrades gracefully instead of going silent - both on
a real system with restricted network, and specifically for the demo dataset
on any machine/venue network.
"""

import os
import gzip
import json
import subprocess
from dotenv import load_dotenv

load_dotenv()

_AI_AVAILABLE = False
_CLIENT = None
_MODEL_NAME = "gemini-3.6-flash"

try:
    from google import genai
    from google.genai import types
    _api_key = os.environ.get("GEMINI_API_KEY")
    if _api_key:
        _CLIENT = genai.Client(api_key=_api_key)
        http_options=types.HttpOptions(timeout=8000)
        _AI_AVAILABLE = True
except Exception:
    _AI_AVAILABLE = False


CHANGELOG_SYSTEM_PROMPT = """You are a Linux systems risk analyst. You are given \
the raw changelog text for a package. Your job is to identify CONCRETE risk \
indicators mentioned in the text itself - things a version number alone could \
never reveal.

Look specifically for: breaking changes, removed/deprecated features, changed \
defaults or config formats, security-sensitive fixes that alter behavior, \
required reboots or manual migration steps, and known regressions mentioned \
by the maintainers themselves.

Rules:
- Only cite risks that are ACTUALLY present in the provided text. Do not invent any.
- If the changelog is routine (bug fixes, translations, minor patches) with no
  concerning content, say so plainly - do not manufacture risk.
- risk_contribution must be an integer 0-30 (this is ADDED to a separate
  structural risk score, so keep it proportional - routine changes should
  score near 0, genuine breaking changes near 30).
- citation must be a short, near-verbatim reference to the specific line(s)
  that justify the score (or empty string if risk_contribution is 0).
- Respond ONLY in raw JSON with keys: "risk_contribution", "citation", "summary".
"""


# Reference changelog snippets for the CURATED DEMO DATASET packages only
# (fictional example versions like "nvidia-driver-535 535.183.01" that aren't
# actually installed anywhere, so neither the live nor local strategy can
# find real data for them). Since the demo dataset is already explicitly
# labeled as curated/illustrative (source: "demo_dataset" in the API
# response), using realistic reference text here for THOSE SPECIFIC packages
# keeps the demo reliable on any network/machine without misrepresenting
# real system data - this fallback only ever triggers after both real
# strategies (live, local) have already failed.
_DEMO_REFERENCE_CHANGELOGS = {
    "nvidia-driver-535": """nvidia-driver-535 (535.183.01) noble; urgency=medium

  * Updated Xorg driver ABI compatibility layer - requires a full reboot,
    not just a display server restart, for the new kernel module to load.
  * Changed default power management mode on laptops with hybrid graphics;
    users relying on the previous behavior should check /etc/nvidia/ after
    updating.
  * Fixed a race condition in nvidia_drm module init that could cause a
    black screen on first boot after driver load on certain multi-monitor
    configurations.

 -- NVIDIA Linux Team <linux-bugs@nvidia.com>  Tue, 15 Jul 2026 09:00:00 +0000""",

    "linux-image-6.8.0-49-generic": """linux (6.8.0-49.49) noble; urgency=medium

  * New upstream kernel release - includes updated NVIDIA/AMD DRM driver
    interfaces; third-party out-of-tree drivers (e.g. proprietary GPU
    drivers) may need to be rebuilt or reinstalled after this update.
  * Requires a reboot to take effect; the running kernel is not replaced
    until next boot.
  * Security fixes for multiple CVEs in the network stack and USB subsystem.

 -- Ubuntu Kernel Team <kernel-team@lists.ubuntu.com>  Mon, 14 Jul 2026 12:00:00 +0000""",
}


def fetch_changelog(package_name, max_lines=40, timeout=6):
    """
    Fetches a package's changelog with three strategies, tried in order:

    1. LIVE (network): `apt-get changelog <pkg>` - gets the exact entry for
       the pending update itself, most accurate, but depends on reaching
       changelogs.ubuntu.com (can be slow/blocked on restrictive networks -
       including, notably, conference/venue wifi during a live demo).
    2. LOCAL (offline, on-disk): every installed Debian/Ubuntu package ships
       its own changelog at /usr/share/doc/<pkg>/changelog.Debian.gz (or
       changelog.gz). This doesn't require network at all, and still gives
       genuinely useful real content.
    3. REFERENCE: curated text for known demo-dataset packages only, used
       only if both real strategies above found nothing.

    Returns:
        (changelog_text, source) where source is "live", "local",
        "reference", or None. changelog_text is None if everything failed.
    """
    # Strategy 1: live network fetch (most accurate - exact pending version)
    try:
        result = subprocess.run(
            ["apt-get", "changelog", package_name],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            return "\n".join(lines[:max_lines]), "live"
    except Exception:
        pass

    # Strategy 2: local on-disk changelog (no network required)
    for fname in ("changelog.Debian.gz", "changelog.gz"):
        path = f"/usr/share/doc/{package_name}/{fname}"
        if os.path.isfile(path):
            try:
                with gzip.open(path, "rt", errors="replace") as f:
                    content = f.read()
                lines = content.strip().splitlines()
                if lines:
                    return "\n".join(lines[:max_lines]), "local"
            except Exception:
                continue

    # Strategy 3: curated reference text for demo-dataset-only packages
    if package_name in _DEMO_REFERENCE_CHANGELOGS:
        return _DEMO_REFERENCE_CHANGELOGS[package_name], "reference"

    return None, None


def analyze_changelog(package_name, changelog_text):
    """
    Sends real changelog text to the AI for semantic risk analysis.

    Returns:
        dict with 'risk_contribution' (int 0-30), 'citation' (str), 'summary' (str)
        or None if AI unavailable / changelog unavailable.
    """
    if not _AI_AVAILABLE or not changelog_text:
        return None

    try:
        response = _CLIENT.models.generate_content(
            model=_MODEL_NAME,
            contents=f"Package: {package_name}\n\nChangelog:\n{changelog_text}",
            config=types.GenerateContentConfig(
                system_instruction=CHANGELOG_SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )

        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)

        contribution = int(parsed.get("risk_contribution", 0))
        contribution = max(0, min(contribution, 30))

        return {
            "risk_contribution": contribution,
            "citation": parsed.get("citation", "").strip(),
            "summary": parsed.get("summary", "").strip(),
        }

    except Exception as e:
        print(f"[SentinelUpdate] Changelog analysis failed for {package_name}: {e}")
        return None

def enrich_with_changelog_analysis(scored_updates, max_packages=3):
    """
    Enriches already-scored updates with semantic changelog analysis, for
    up to `max_packages` (to control latency/cost - only worth doing for the
    updates that matter, so callers should pass the highest-scoring ones).

    Mutates and returns the list: adds 'semantic_analysis' key to each item
    that was analyzed, and bumps 'score' by the risk_contribution (capped 100).

    ALWAYS records what happened for each attempted package - even when the
    changelog couldn't be fetched from any source - by appending a status
    signal. Silent no-ops are exactly what an explainability-first tool
    should never do.
    """
    for item in scored_updates[:max_packages]:
        pkg = item["package"]
        changelog, source = fetch_changelog(pkg)

        if changelog is None:
            item["semantic_analysis"] = {"status": "unavailable"}
            item["signals"].append(
                "Changelog analysis attempted but unavailable (no network access "
                "and no local changelog found for this package)."
            )
            continue

        analysis = analyze_changelog(pkg, changelog)
        if not analysis:
            item["semantic_analysis"] = {"status": "ai_unavailable", "source": source}
            item["signals"].append(
                f"Changelog was fetched ({source}) but AI analysis could not run " )
            continue

        item["semantic_analysis"] = {**analysis, "status": "ok", "source": source}
        source_label = {
            "live": "live changelog",
            "local": "local changelog cache (offline)",
            "reference": "reference example (demo dataset)",
        }.get(source, source)
        if analysis["risk_contribution"] > 0:
            item["score"] = min(100, item["score"] + analysis["risk_contribution"])
            item["signals"].append(
                f"Changelog analysis ({source_label}): {analysis['summary']} "
                f"(cited: \"{analysis['citation']}\")"
            )
            if item["score"] >= 70:
                item["level"] = "HIGH"
            elif item["score"] >= 40:
                item["level"] = "MEDIUM"
        else:
            item["signals"].append(
                f"Changelog analysis ({source_label}): reviewed, no additional risk found. "
                f"{analysis.get('summary', '')}".strip()
            )
    return scored_updates


if __name__ == "__main__":
    print(f"AI available: {_AI_AVAILABLE}")
    text, source = fetch_changelog("curl")
    print(f"fetch_changelog('curl') -> source={source}, {len(text or '')} chars")
    if text:
        print(text[:300])