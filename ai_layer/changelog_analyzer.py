def enrich_with_changelog_analysis(scored_updates, max_packages=5):
    """
    Enriches already-scored updates with semantic changelog analysis, for
    up to `max_packages` (to control latency/cost - only worth doing for the
    updates that matter, so callers should pass the highest-scoring ones).

    Mutates and returns the list: adds 'semantic_analysis' key to each item
    that was analyzed, and bumps 'score' by the risk_contribution (capped 100).

    IMPORTANT: this ALWAYS records what happened for each attempted package -
    even when the changelog couldn't be fetched (no network, offline, no
    changelog available for that package) - by appending a status signal.
    An earlier version silently did nothing on failure, which made "deep
    analysis on" and "deep analysis off" look identical with no visible
    explanation why. Silent no-ops are exactly what an explainability-first
    tool should never do.
    """
    for item in scored_updates[:max_packages]:
        changelog = fetch_changelog(item["package"])

        if changelog is None:
            item["semantic_analysis"] = {"status": "unavailable"}
            item["signals"].append(
                "Changelog analysis attempted but unavailable (no network access "
                "to changelogs.ubuntu.com, or no changelog published for this package)."
            )
            continue

        analysis = analyze_changelog(item["package"], changelog)
        if not analysis:
            item["semantic_analysis"] = {"status": "ai_unavailable"}
            item["signals"].append(
                "Changelog was fetched but AI analysis could not run (no GEMINI_API_KEY configured)."
            )
            continue

        item["semantic_analysis"] = {**analysis, "status": "ok"}
        if analysis["risk_contribution"] > 0:
            item["score"] = min(100, item["score"] + analysis["risk_contribution"])
            item["signals"].append(
                f"Changelog analysis: {analysis['summary']} "
                f"(cited: \"{analysis['citation']}\")"
            )
            if item["score"] >= 70:
                item["level"] = "HIGH"
            elif item["score"] >= 40:
                item["level"] = "MEDIUM"
        else:
            item["signals"].append(
                f"Changelog analysis: reviewed, no additional risk found. {analysis.get('summary', '')}".strip()
            )
    return scored_updates