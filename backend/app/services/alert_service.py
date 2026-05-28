"""Alert service — Discord and Slack webhook notifications for DevOps events.

Sends structured embeds/blocks for:
- Deployment incidents (anomaly detected)
- Rollback triggered / completed
- Deployment risk warnings
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

# ── Colour constants ──────────────────────────────────────────────────────────

_COLOUR = {
    "critical": 0xE53E3E,  # red
    "high": 0xED8936,      # orange
    "medium": 0xECC94B,    # yellow
    "low": 0x48BB78,       # green
    "info": 0x4299E1,      # blue
    "rollback": 0x9F7AEA,  # purple
}


# ── Public send helpers ───────────────────────────────────────────────────────

async def send_incident_alert(
    *,
    discord_url: str | None,
    slack_url: str | None,
    project_name: str,
    deployment_id: UUID,
    incident_type: str,
    severity: str,
    summary: str,
    root_cause: str,
    recommended_action: str,
    rollback_confidence: float,
    preview_url: str | None = None,
) -> None:
    """Notify configured channels about a deployment incident."""
    title = f"🚨 Deployment Incident — {severity.upper()}"
    colour = _COLOUR.get(severity.lower(), _COLOUR["medium"])

    fields_discord = [
        {"name": "Project", "value": project_name, "inline": True},
        {"name": "Incident type", "value": incident_type, "inline": True},
        {"name": "Summary", "value": summary[:1000], "inline": False},
        {"name": "Root cause", "value": root_cause[:500], "inline": False},
        {"name": "Recommended action", "value": recommended_action.upper(), "inline": True},
        {"name": "Rollback confidence", "value": f"{rollback_confidence:.0%}", "inline": True},
    ]
    if preview_url:
        fields_discord.append({"name": "URL", "value": preview_url[:200], "inline": False})

    fields_slack = [
        {"type": "mrkdwn", "text": f"*Project:* {project_name}"},
        {"type": "mrkdwn", "text": f"*Incident:* {incident_type} ({severity})"},
        {"type": "mrkdwn", "text": f"*Summary:* {summary[:500]}"},
        {"type": "mrkdwn", "text": f"*Root cause:* {root_cause[:300]}"},
        {"type": "mrkdwn", "text": f"*Action:* {recommended_action.upper()}  |  confidence {rollback_confidence:.0%}"},
    ]

    await _send_discord(discord_url, title=title, description="", colour=colour, fields=fields_discord)
    await _send_slack(slack_url, title=title, fields=fields_slack, colour_hex=_hex(colour))


async def send_rollback_alert(
    *,
    discord_url: str | None,
    slack_url: str | None,
    project_name: str,
    deployment_id: UUID,
    triggered_by: str,
    status: str,
    reason: str,
    previous_deployment_id: UUID | None = None,
) -> None:
    """Notify channels about a rollback event."""
    emoji = "✅" if status == "completed" else ("❌" if status == "failed" else "🔄")
    title = f"{emoji} Rollback {status.upper()} — {project_name}"
    colour = _COLOUR["rollback"] if status == "completed" else _COLOUR["critical"]

    fields_discord = [
        {"name": "Project", "value": project_name, "inline": True},
        {"name": "Triggered by", "value": triggered_by, "inline": True},
        {"name": "Status", "value": status.upper(), "inline": True},
        {"name": "Reason", "value": reason[:800], "inline": False},
    ]
    if previous_deployment_id:
        fields_discord.append({
            "name": "Rolled back to",
            "value": str(previous_deployment_id)[:8] + "…",
            "inline": True,
        })

    fields_slack = [
        {"type": "mrkdwn", "text": f"*Project:* {project_name}"},
        {"type": "mrkdwn", "text": f"*Triggered by:* {triggered_by}  |  *Status:* {status.upper()}"},
        {"type": "mrkdwn", "text": f"*Reason:* {reason[:500]}"},
    ]

    await _send_discord(discord_url, title=title, description="", colour=colour, fields=fields_discord)
    await _send_slack(slack_url, title=title, fields=fields_slack, colour_hex=_hex(colour))


async def send_risk_warning(
    *,
    discord_url: str | None,
    slack_url: str | None,
    project_name: str,
    risk_score: float,
    risk_level: str,
    reasoning: str,
    risk_factors: list[str],
    branch_name: str = "",
) -> None:
    """Warn channels about a high-risk pre-deploy assessment."""
    if risk_level not in ("high", "critical"):
        return  # only alert for high+ risk

    title = f"⚠️ High-Risk Deploy Detected — {project_name}"
    colour = _COLOUR.get(risk_level, _COLOUR["high"])
    factors_str = "\n".join(f"• {f}" for f in risk_factors[:5]) or "(none)"

    fields_discord = [
        {"name": "Risk level", "value": risk_level.upper(), "inline": True},
        {"name": "Risk score", "value": f"{risk_score:.2f}", "inline": True},
        {"name": "Branch", "value": branch_name or "(unknown)", "inline": True},
        {"name": "Reasoning", "value": reasoning[:600], "inline": False},
        {"name": "Risk factors", "value": factors_str, "inline": False},
    ]
    fields_slack = [
        {"type": "mrkdwn", "text": f"*Project:* {project_name}  |  *Risk:* {risk_level.upper()} ({risk_score:.2f})"},
        {"type": "mrkdwn", "text": f"*Branch:* {branch_name or '(unknown)'}"},
        {"type": "mrkdwn", "text": f"*Reasoning:* {reasoning[:400]}"},
        {"type": "mrkdwn", "text": f"*Factors:*\n{factors_str}"},
    ]

    await _send_discord(discord_url, title=title, description="", colour=colour, fields=fields_discord)
    await _send_slack(slack_url, title=title, fields=fields_slack, colour_hex=_hex(colour))


# ── Low-level send ────────────────────────────────────────────────────────────

async def _send_discord(
    url: str | None,
    *,
    title: str,
    description: str,
    colour: int,
    fields: list[dict],
) -> None:
    if not url:
        return
    payload = {
        "embeds": [{
            "title": title[:256],
            "description": description[:4000],
            "color": colour,
            "fields": fields[:25],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code not in (200, 204):
            logger.warning("Discord webhook returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Discord webhook send failed: %s", exc)


async def _send_slack(
    url: str | None,
    *,
    title: str,
    fields: list[dict],
    colour_hex: str,
) -> None:
    if not url:
        return
    # Slack attachment with side colour bar
    payload = {
        "attachments": [{
            "color": colour_hex,
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": title[:150], "emoji": True},
                },
                {
                    "type": "section",
                    "fields": [f for f in fields[:10]],
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn",
                         "text": f"<!date^{int(datetime.now(timezone.utc).timestamp())}^{{date_short_pretty}} {{time_secs}}|{datetime.now(timezone.utc).isoformat()}>"},
                    ],
                },
            ],
        }]
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Slack webhook send failed: %s", exc)


def _hex(colour: int) -> str:
    return f"#{colour:06X}"
