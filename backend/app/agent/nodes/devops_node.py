"""DevOps AI node — risk assessment, incident analysis, rollback reasoning.

Phase 4 AI layer:
- Pre-deploy risk scoring: estimates blast radius, detects risky changes
- Incident analysis: explains anomaly detected in health metrics
- Rollback reasoning: explains why rollback was triggered + what to expect

All functions are pure (no DB access) and return structured dataclasses.
Falls back to rule-based analysis if LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ── Safety patterns ────────────────────────────────────────────────────────────

_HIGH_RISK_PATTERNS = [
    r"alembic.*versions|migration.*\.py",
    r"drop\s+table|truncate\s+table|delete\s+from",
    r"alter\s+table.*drop\s+column",
    r"auth.*\.py|security.*\.py",
    r"settings\.py|config\.py",
    r"\.env$|secrets\.",
    r"password|secret.*key|api.*key",
    r"remove_column|rename_column",
]

_MEDIUM_RISK_PATTERNS = [
    r"requirements.*\.txt|pyproject\.toml|package\.json",
    r"dockerfile|docker-compose",
    r"\.github/workflows",
    r"add_column.*not.*null|nullable.*false",
    r"foreign.*key|create.*index",
]


@dataclass
class RiskAssessment:
    """Pre-deployment risk assessment."""
    risk_score: float           # 0.0–1.0
    risk_level: str             # 'low' | 'medium' | 'high' | 'critical'
    reasoning: str              # plain-language explanation
    risk_factors: list[str] = field(default_factory=list)
    blast_radius: str = ""      # "affects N files, touches auth/DB/API"
    safe_to_deploy: bool = True
    ai_raw_response: str = ""
    via_llm: bool = False


@dataclass
class IncidentAnalysis:
    """AI explanation of a detected deployment incident."""
    severity: str               # 'low' | 'medium' | 'high' | 'critical'
    summary: str                # one-line summary
    root_cause: str
    recommended_action: str     # 'rollback' | 'monitor' | 'investigate' | 'ignore'
    rollback_confidence: float  # 0.0–1.0 confidence that rollback is right move
    reasoning: str
    via_llm: bool = False


# ── Public entry points ───────────────────────────────────────────────────────

async def assess_deployment_risk(
    *,
    files_changed: list[str],
    commit_message: str = "",
    branch_name: str = "",
    step_results: dict[str, str] | None = None,
    previous_risk_scores: list[float] | None = None,
) -> RiskAssessment:
    """Estimate deployment risk before production deploy.

    Args:
        files_changed: List of file paths modified in this deployment.
        commit_message: Git commit message.
        branch_name: Branch being deployed.
        step_results: Dict of {step_key: status} from pipeline steps.
        previous_risk_scores: Recent deployment risk scores for trend.
    """
    from app.llm.factory import architect_llm_configured

    if architect_llm_configured():
        try:
            return await _llm_risk_assessment(
                files_changed=files_changed,
                commit_message=commit_message,
                branch_name=branch_name,
                step_results=step_results or {},
                previous_risk_scores=previous_risk_scores or [],
            )
        except Exception as exc:
            logger.warning("devops_node risk LLM failed (%s), using heuristics", exc)

    return _heuristic_risk_assessment(
        files_changed=files_changed,
        commit_message=commit_message,
        step_results=step_results or {},
    )


async def analyze_incident(
    *,
    incident_type: str,
    consecutive_failures: int,
    latest_http_status: int | None,
    latest_latency_ms: int | None,
    deployment_age_minutes: float,
    preview_url: str | None,
) -> IncidentAnalysis:
    """Analyze a deployment health incident and recommend action."""
    from app.llm.factory import architect_llm_configured

    if architect_llm_configured():
        try:
            return await _llm_incident_analysis(
                incident_type=incident_type,
                consecutive_failures=consecutive_failures,
                latest_http_status=latest_http_status,
                latest_latency_ms=latest_latency_ms,
                deployment_age_minutes=deployment_age_minutes,
                preview_url=preview_url,
            )
        except Exception as exc:
            logger.warning("devops_node incident LLM failed (%s), using heuristics", exc)

    return _heuristic_incident_analysis(
        incident_type=incident_type,
        consecutive_failures=consecutive_failures,
        latest_http_status=latest_http_status,
    )


# ── LLM risk assessment ───────────────────────────────────────────────────────

_RISK_SYSTEM = """\
You are a senior DevOps engineer performing a pre-deployment risk assessment.
Your job is to estimate how risky this deployment is and explain why.

Risk factors to consider:
- Database migrations (especially destructive ones)
- Auth/security changes
- Breaking API changes
- Infrastructure config changes
- Large changeset (blast radius)
- Dependency upgrades
- Recent failure history

Respond ONLY with valid JSON, no markdown fences.
"""

_RISK_HUMAN_TEMPLATE = """\
Assess the deployment risk for this code change.

Branch: {branch}
Commit message: {commit_message}
Files changed ({file_count}):
{files_list}

Pipeline step results:
{step_results}

Previous risk scores (last 5 deploys): {prev_scores}

Respond with EXACTLY this JSON:
{{
  "risk_score": 0.0,
  "risk_level": "low",
  "reasoning": "...",
  "risk_factors": ["..."],
  "blast_radius": "...",
  "safe_to_deploy": true
}}

risk_level must be: "low" | "medium" | "high" | "critical"
risk_score: 0.0-1.0
safe_to_deploy: false only if risk_level is "critical" or contains destructive DB migration
"""


async def _llm_risk_assessment(
    *,
    files_changed: list[str],
    commit_message: str,
    branch_name: str,
    step_results: dict[str, str],
    previous_risk_scores: list[float],
) -> RiskAssessment:
    from app.llm.factory import create_architect_llm
    from app.llm.invoke_helpers import ainvoke_llm

    files_list = "\n".join(f"  {f}" for f in files_changed[:50]) or "  (no file list available)"
    step_str = ", ".join(f"{k}={v}" for k, v in step_results.items()) or "N/A"
    prev_str = str([round(s, 2) for s in previous_risk_scores]) if previous_risk_scores else "[]"

    prompt = _RISK_HUMAN_TEMPLATE.format(
        branch=branch_name or "(unknown)",
        commit_message=commit_message[:200] or "(no message)",
        file_count=len(files_changed),
        files_list=files_list,
        step_results=step_str,
        prev_scores=prev_str,
    )

    messages = [SystemMessage(content=_RISK_SYSTEM), HumanMessage(content=prompt)]
    llm = create_architect_llm(temperature=0.1)
    t0 = time.monotonic()
    response = await (await __import__('app.llm.invoke_helpers', fromlist=['ainvoke_llm'])).ainvoke_llm(llm, messages)
    logger.debug("devops_node risk LLM: %.0fms", (time.monotonic() - t0) * 1000)

    raw = str(getattr(response, "content", response))
    parsed = _parse_json(raw)

    risk_score = float(parsed.get("risk_score", 0.5))
    risk_level = str(parsed.get("risk_level", "medium"))
    return RiskAssessment(
        risk_score=min(1.0, max(0.0, risk_score)),
        risk_level=risk_level,
        reasoning=str(parsed.get("reasoning", "")),
        risk_factors=list(parsed.get("risk_factors", [])),
        blast_radius=str(parsed.get("blast_radius", "")),
        safe_to_deploy=bool(parsed.get("safe_to_deploy", True)),
        ai_raw_response=raw[:4000],
        via_llm=True,
    )


# ── LLM incident analysis ─────────────────────────────────────────────────────

_INCIDENT_SYSTEM = """\
You are an SRE (Site Reliability Engineer) analyzing a deployment incident.
Given health check metrics, explain what went wrong and recommend action.

Possible actions:
- rollback: immediately revert to previous deployment
- monitor: continue watching, not severe enough to rollback yet
- investigate: alert engineering team to investigate manually
- ignore: likely transient/fluke, no action needed

Respond ONLY with valid JSON.
"""

_INCIDENT_HUMAN_TEMPLATE = """\
A deployment health incident was detected:

Incident type: {incident_type}
Consecutive health check failures: {consecutive_failures}
Latest HTTP status: {http_status}
Latest latency: {latency_ms}ms
Deployment age when detected: {age_minutes:.1f} minutes
Preview URL: {preview_url}

Respond with:
{{
  "severity": "medium",
  "summary": "...",
  "root_cause": "...",
  "recommended_action": "rollback",
  "rollback_confidence": 0.0,
  "reasoning": "..."
}}
"""


async def _llm_incident_analysis(
    *,
    incident_type: str,
    consecutive_failures: int,
    latest_http_status: int | None,
    latest_latency_ms: int | None,
    deployment_age_minutes: float,
    preview_url: str | None,
) -> IncidentAnalysis:
    from app.llm.factory import create_architect_llm
    from app.llm.invoke_helpers import ainvoke_llm

    prompt = _INCIDENT_HUMAN_TEMPLATE.format(
        incident_type=incident_type,
        consecutive_failures=consecutive_failures,
        http_status=latest_http_status or "N/A",
        latency_ms=latest_latency_ms or "N/A",
        age_minutes=deployment_age_minutes,
        preview_url=preview_url or "(unknown)",
    )
    messages = [SystemMessage(content=_INCIDENT_SYSTEM), HumanMessage(content=prompt)]
    llm = create_architect_llm(temperature=0.1)
    response = await ainvoke_llm(llm, messages)

    raw = str(getattr(response, "content", response))
    parsed = _parse_json(raw)

    return IncidentAnalysis(
        severity=str(parsed.get("severity", "medium")),
        summary=str(parsed.get("summary", "Deployment incident detected")),
        root_cause=str(parsed.get("root_cause", "Unknown")),
        recommended_action=str(parsed.get("recommended_action", "monitor")),
        rollback_confidence=float(parsed.get("rollback_confidence", 0.5)),
        reasoning=str(parsed.get("reasoning", "")),
        via_llm=True,
    )


# ── Heuristic fallbacks ───────────────────────────────────────────────────────

def _heuristic_risk_assessment(
    *,
    files_changed: list[str],
    commit_message: str,
    step_results: dict[str, str],
) -> RiskAssessment:
    risk_score = 0.1
    risk_factors: list[str] = []
    files_lower = [f.lower() for f in files_changed]
    combined_text = commit_message.lower() + " ".join(files_lower)

    # High-risk patterns
    for pat in _HIGH_RISK_PATTERNS:
        if any(re.search(pat, f, re.I) for f in files_lower) or re.search(pat, combined_text, re.I):
            risk_score += 0.25
            label = pat.split(r"|")[0].replace(r"\.", ".").replace(r"\s+", " ").strip("^$")
            risk_factors.append(f"High-risk pattern: {label}")

    # Medium-risk patterns
    for pat in _MEDIUM_RISK_PATTERNS:
        if any(re.search(pat, f, re.I) for f in files_lower):
            risk_score += 0.1
            risk_factors.append(f"Config change: {pat.split('|')[0][:30]}")

    # Blast radius
    n = len(files_changed)
    if n > 20:
        risk_score += 0.15
        risk_factors.append(f"Large changeset: {n} files modified")
    elif n > 10:
        risk_score += 0.07
        risk_factors.append(f"Medium changeset: {n} files modified")

    # Step failures
    failed_steps = [k for k, v in step_results.items() if v == "failure"]
    if failed_steps:
        risk_score += 0.2
        risk_factors.append(f"Pipeline step(s) failed: {', '.join(failed_steps)}")

    risk_score = min(1.0, risk_score)
    risk_level = (
        "critical" if risk_score >= 0.85
        else "high" if risk_score >= 0.6
        else "medium" if risk_score >= 0.35
        else "low"
    )

    return RiskAssessment(
        risk_score=round(risk_score, 2),
        risk_level=risk_level,
        reasoning=(
            f"Heuristic analysis: {len(risk_factors)} risk factor(s) detected. "
            + ("; ".join(risk_factors[:3]) if risk_factors else "No significant risks detected.")
        ),
        risk_factors=risk_factors,
        blast_radius=f"Affects {n} file(s)",
        safe_to_deploy=risk_level not in ("critical",),
        via_llm=False,
    )


def _heuristic_incident_analysis(
    *,
    incident_type: str,
    consecutive_failures: int,
    latest_http_status: int | None,
) -> IncidentAnalysis:
    is_server_error = (latest_http_status or 0) >= 500
    is_total_failure = (latest_http_status or 0) == 0 or incident_type == "health_fail"

    if consecutive_failures >= 3 or is_total_failure:
        severity = "critical"
        action = "rollback"
        confidence = 0.9
        summary = "Deployment unreachable or returning server errors"
    elif consecutive_failures == 2 or is_server_error:
        severity = "high"
        action = "rollback"
        confidence = 0.75
        summary = f"Multiple consecutive health failures (HTTP {latest_http_status})"
    else:
        severity = "medium"
        action = "monitor"
        confidence = 0.4
        summary = f"Health degradation detected (type={incident_type})"

    return IncidentAnalysis(
        severity=severity,
        summary=summary,
        root_cause=f"Deployment health check failed {consecutive_failures}x (type={incident_type})",
        recommended_action=action,
        rollback_confidence=confidence,
        reasoning=f"Heuristic: {consecutive_failures} consecutive failures, HTTP {latest_http_status}",
        via_llm=False,
    )


# ── JSON parser ───────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", clean)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}
