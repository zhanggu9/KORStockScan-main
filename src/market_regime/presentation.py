from __future__ import annotations

from typing import Any


def summarize_market_regime(risk_state: str | None) -> dict[str, Any]:
    normalized = str(risk_state or "").upper()
    if normalized == "RISK_ON":
        return {
            "regime_code": "BULL",
            "risk_state": normalized,
            "status_text": "상승장",
            "status_tone": "good",
            "emoji": "🐂",
        }
    if normalized == "NEUTRAL":
        return {
            "regime_code": "NEUTRAL",
            "risk_state": normalized,
            "status_text": "조정장",
            "status_tone": "warn",
            "emoji": "🐻",
        }
    if normalized == "RISK_OFF":
        return {
            "regime_code": "BEAR",
            "risk_state": normalized,
            "status_text": "하락장",
            "status_tone": "bad",
            "emoji": "🐻",
        }
    return {
        "regime_code": "UNKNOWN",
        "risk_state": normalized or "UNKNOWN",
        "status_text": "데이터 부족",
        "status_tone": "muted",
        "emoji": "❔",
    }


def summarize_market_regime_snapshot(snapshot: Any) -> dict[str, Any]:
    summary = summarize_market_regime(getattr(snapshot, "risk_state", None))
    summary["allow_swing_entry"] = bool(getattr(snapshot, "allow_swing_entry", False))
    summary["swing_score"] = int(getattr(snapshot, "swing_score", 0) or 0)
    return summary
