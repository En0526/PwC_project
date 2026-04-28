"""Agent 1: identify the user-requested section and build a stable snapshot."""
from __future__ import annotations

from backend.services.site_profiles import SectionSnapshot, extract_known_section_snapshot


def extract_section_snapshot(
    *,
    url: str,
    html: str,
    full_text: str,
    watch_description: str | None = None,
) -> SectionSnapshot | None:
    """
    Return a deterministic section snapshot when a known site profile matches.

    Unknown sites intentionally return None so the caller can fall back to the
    existing Gemini section extractor or whole-page monitoring.
    """
    return extract_known_section_snapshot(
        url=url,
        html=html,
        full_text=full_text,
        watch_description=watch_description,
    )
