#!/usr/bin/env python3
"""
n8n Failed Runs plugin for CheckMK

Consumes the '<<<n8n_failed_runs>>>' section produced by the special agent when
'Failed Runs Analysis' is enabled.  The section was previously collected but
never parsed, so the whole failure analysis was discarded.

Section layout:
  summary;<wf_with_executions>;<wf_with_failures_24h>;<failures_24h>;<failures_8h>;<rate_24h>;<rate_8h>
  workflow;<id>;<name>;<total>;<failed>;<successful>;<rate>;<total_24h>;<failed_24h>;<ok_24h>;<rate_24h>;<avg_dur>;<p95>;<p99>;<recent_count>
  failure;<wf_id>;<exec_id>;<wf_name>;<node>;<message>;<started_at>;<finished_at>;<duration>
"""

from typing import Dict, List, Optional

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    check_levels,
    Result,
    Service,
    State,
    StringTable,
)


def _as_levels(levels):
    """Turn a normalized ``(warn, crit)`` pair into the ``check_levels`` shape."""
    return ("fixed", levels) if levels else ("no_levels", None)


def _to_float(raw: str, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _to_int(raw: str, default: int = 0) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def parse_n8n_failed_runs(string_table: StringTable) -> Optional[Dict]:
    if not string_table:
        return None

    data: Dict = {
        "workflows_with_executions": 0,
        "workflows_with_failures_24h": 0,
        "total_failures_24h": 0,
        "total_failures_8h": 0,
        "global_success_rate_24h": 100.0,
        "global_success_rate_8h": 100.0,
        "workflows": [],
        "failures": [],
    }

    for line in string_table:
        parts = " ".join(line).split(";")
        if not parts:
            continue
        kind = parts[0]

        if kind == "summary" and len(parts) >= 7:
            data["workflows_with_executions"] = _to_int(parts[1])
            data["workflows_with_failures_24h"] = _to_int(parts[2])
            data["total_failures_24h"] = _to_int(parts[3])
            data["total_failures_8h"] = _to_int(parts[4])
            data["global_success_rate_24h"] = _to_float(parts[5], 100.0)
            data["global_success_rate_8h"] = _to_float(parts[6], 100.0)

        elif kind == "workflow" and len(parts) >= 15:
            data["workflows"].append({
                "workflow_id": parts[1],
                "workflow_name": parts[2],
                "total": _to_int(parts[3]),
                "failed": _to_int(parts[4]),
                "successful": _to_int(parts[5]),
                "success_rate": _to_float(parts[6]),
                "total_24h": _to_int(parts[7]),
                "failed_24h": _to_int(parts[8]),
                "successful_24h": _to_int(parts[9]),
                "success_rate_24h": _to_float(parts[10]),
                "avg_duration": _to_float(parts[11]),
                "p95": _to_float(parts[12]),
                "p99": _to_float(parts[13]),
                "recent_count": _to_int(parts[14]),
            })

        elif kind == "failure" and len(parts) >= 9:
            data["failures"].append({
                "workflow_id": parts[1],
                "execution_id": parts[2],
                "workflow_name": parts[3],
                "node": parts[4],
                "message": parts[5],
                "started_at": parts[6],
                "finished_at": parts[7],
                "duration": _to_float(parts[8]),
            })

    return data


def discover_n8n_failed_runs(section: Optional[Dict]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def check_n8n_failed_runs(params: Dict, section: Optional[Dict]) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No failed runs data available")
        return

    failures_24h = section["total_failures_24h"]
    failures_8h = section["total_failures_8h"]
    rate_24h = section["global_success_rate_24h"]
    affected = section["workflows_with_failures_24h"]

    yield Result(
        state=State.OK,
        summary=(
            f"{failures_24h} failures in 24h across {affected} workflow(s) - "
            f"{rate_24h:.1f}% global success rate"
        ),
    )

    # State and perfdata thresholds come from the same levels, so the graphs
    # show where warn/crit sit.
    yield from check_levels(
        failures_24h,
        levels_upper=_as_levels(_normalize_levels(params.get("failures_24h"), (10, 50))),
        metric_name="n8n_failures_24h",
        label="Failures (24h)",
        render_func=lambda v: f"{v:.0f}",
        notice_only=True,
    )
    yield from check_levels(
        rate_24h,
        levels_lower=_as_levels(
            _normalize_levels(params.get("global_success_rate_24h"), (95.0, 80.0))
        ),
        metric_name="n8n_global_success_rate_24h",
        label="Global success rate (24h)",
        render_func=lambda v: f"{v:.1f}%",
        notice_only=True,
    )
    yield Result(state=State.OK, summary=f"8h: {failures_8h} failures ({section['global_success_rate_8h']:.1f}% success)")

    # Per workflow breakdown, worst first.
    worst: List[Dict] = sorted(
        (w for w in section["workflows"] if w["failed_24h"] > 0),
        key=lambda w: w["failed_24h"],
        reverse=True,
    )
    for wf in worst[:5]:
        name = wf["workflow_name"] or wf["workflow_id"]
        detail = f"{name}: {wf['failed_24h']} failures in 24h ({wf['success_rate_24h']:.1f}% success)"
        if wf["p95"] > 0:
            detail += f", P95 {wf['p95']:.1f}s / P99 {wf['p99']:.1f}s"
        yield Result(state=State.OK, notice=detail)

    # Most recent individual failures, so the reason is visible in the service.
    for failure in section["failures"][:5]:
        message = failure["message"] or "Unknown error"
        if len(message) > 60:
            message = message[:57] + "..."
        node = failure["node"]
        where = f" at node '{node}'" if node and node != "unknown" else ""
        yield Result(
            state=State.OK,
            notice=(
                f"Execution {failure['execution_id']}{where}: {message} "
                f"({failure['started_at']})"
            ),
        )

    yield Metric("n8n_failures_8h", failures_8h)
    yield Metric("n8n_global_success_rate_8h", section["global_success_rate_8h"])
    yield Metric("n8n_workflows_with_failures_24h", affected)


def _normalize_levels(param_value, default=None):
    """Return a plain ``(warn, crit)`` tuple for any threshold parameter shape.

    Same contract as in the other n8n plugins: ``SimpleLevels`` stores its
    value as ``("fixed", (warn, crit))`` or ``("no_levels", None)``, which must
    never be unpacked directly.
    """
    if param_value is None:
        return default

    if isinstance(param_value, dict):
        for key in ("levels_upper", "levels_lower"):
            if key in param_value:
                return _normalize_levels(param_value[key], default)
        return default

    if isinstance(param_value, (tuple, list)) and len(param_value) == 2:
        first, second = param_value
        if isinstance(first, str):
            if first == "no_levels":
                return None
            if isinstance(second, (tuple, list)) and len(second) == 2:
                return tuple(second)
            return default
        if isinstance(first, (int, float)) and isinstance(second, (int, float)):
            return (first, second)

    return default


agent_section_n8n_failed_runs = AgentSection(
    name="n8n_failed_runs",
    parse_function=parse_n8n_failed_runs,
)

check_plugin_n8n_failed_runs = CheckPlugin(
    name="n8n_failed_runs",
    sections=["n8n_failed_runs"],
    service_name="n8n Failed Runs",
    discovery_function=discover_n8n_failed_runs,
    check_function=check_n8n_failed_runs,
    check_ruleset_name="n8n_failed_runs",
    # Mirrors the ruleset prefills so the service alerts out of the box
    # instead of staying silent until somebody writes a rule.
    check_default_parameters={
        "failures_24h": ("fixed", (10, 50)),
        "global_success_rate_24h": ("fixed", (95.0, 80.0)),
    },
)
