#!/usr/bin/env python3
"""
n8n Health / Readiness / API status plugins for CheckMK

The special agent already emits the '<<<n8n_healthz>>>', '<<<n8n_readiness>>>'
and '<<<n8n_api_status>>>' sections, but until now nothing consumed them, so
the collected data was discarded.  These plugins turn them into services.
"""

from typing import Dict, Mapping, Optional

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)

# The API surface reported in <<<n8n_api_status>>>.  Endpoints are only
# collected when the corresponding option is enabled in the special agent
# rule, so a 'FAIL' means "enabled but not reachable" only for the endpoints
# the user actually turned on.  Nothing here is CRIT by default; the state is
# driven by the ruleset so that a deliberately disabled endpoint never alarms.
_ENDPOINT_TITLES = {
    "healthz": "Health",
    "readiness": "Readiness",
    "metrics": "Metrics",
    "executions": "Executions",
    "workflows": "Workflows",
    "webhooks": "Webhooks",
    "credentials": "Credentials",
    "users": "Users",
    "tags": "Tags",
    "variables": "Variables",
    "projects": "Projects",
    "failed_runs_analysis": "Failed runs analysis",
}


# --------------------------------------------------------------------------
# <<<n8n_healthz>>>  /  <<<n8n_readiness>>>
#   single line:  <OK|CRIT>;<status_code>;<response_time_seconds>
# --------------------------------------------------------------------------
def _parse_probe(string_table: StringTable) -> Optional[Dict]:
    if not string_table:
        return None

    parts = " ".join(string_table[0]).split(";")
    if not parts or not parts[0]:
        return None

    def _num(raw, cast, default):
        try:
            return cast(raw)
        except (TypeError, ValueError):
            return default

    return {
        "healthy": parts[0].strip().upper() == "OK",
        "status_code": _num(parts[1] if len(parts) > 1 else None, int, 0),
        "response_time": _num(parts[2] if len(parts) > 2 else None, float, 0.0),
    }


def parse_n8n_healthz(string_table: StringTable) -> Optional[Dict]:
    return _parse_probe(string_table)


def parse_n8n_readiness(string_table: StringTable) -> Optional[Dict]:
    return _parse_probe(string_table)


def discover_probe(section: Optional[Dict]) -> DiscoveryResult:
    if section is not None:
        yield Service()


def _check_probe(label: str, section: Optional[Dict]) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary=f"No {label} data available")
        return

    status_code = section["status_code"]
    if section["healthy"]:
        yield Result(state=State.OK, summary=f"{label} OK (HTTP {status_code})")
    else:
        detail = f"HTTP {status_code}" if status_code else "endpoint unreachable"
        yield Result(state=State.CRIT, summary=f"{label} failed ({detail})")

    response_time = section["response_time"]
    if response_time > 0:
        yield Result(state=State.OK, notice=f"Response time: {response_time:.3f}s")
        yield Metric("n8n_response_time", response_time)


def check_n8n_healthz(section: Optional[Dict]) -> CheckResult:
    yield from _check_probe("Health", section)


def check_n8n_readiness(section: Optional[Dict]) -> CheckResult:
    yield from _check_probe("Readiness", section)


agent_section_n8n_healthz = AgentSection(
    name="n8n_healthz",
    parse_function=parse_n8n_healthz,
)

check_plugin_n8n_healthz = CheckPlugin(
    name="n8n_healthz",
    sections=["n8n_healthz"],
    service_name="n8n Health",
    discovery_function=discover_probe,
    check_function=check_n8n_healthz,
)

agent_section_n8n_readiness = AgentSection(
    name="n8n_readiness",
    parse_function=parse_n8n_readiness,
)

check_plugin_n8n_readiness = CheckPlugin(
    name="n8n_readiness",
    sections=["n8n_readiness"],
    service_name="n8n Readiness",
    discovery_function=discover_probe,
    check_function=check_n8n_readiness,
)


# --------------------------------------------------------------------------
# <<<n8n_api_status>>>
#   one line per endpoint:  <endpoint>;<OK|FAIL>
# --------------------------------------------------------------------------
def parse_n8n_api_status(string_table: StringTable) -> Optional[Dict[str, bool]]:
    if not string_table:
        return None

    statuses: Dict[str, bool] = {}
    for line in string_table:
        parts = " ".join(line).split(";")
        if len(parts) >= 2 and parts[0]:
            statuses[parts[0].strip()] = parts[1].strip().upper() == "OK"

    return statuses or None


def discover_n8n_api_status(section: Optional[Dict[str, bool]]) -> DiscoveryResult:
    if section:
        yield Service()


def check_n8n_api_status(
    params: Mapping[str, object],
    section: Optional[Dict[str, bool]],
) -> CheckResult:
    if not section:
        yield Result(state=State.UNKNOWN, summary="No API status data available")
        return

    reachable = sorted(name for name, ok in section.items() if ok)
    failing = sorted(name for name, ok in section.items() if not ok)

    yield Result(
        state=State.OK,
        summary=f"{len(reachable)}/{len(section)} endpoints reachable",
    )

    # An endpoint that is simply not enabled in the rule also reports FAIL, so
    # failures are reported at the state the user chose (OK by default) rather
    # than alarming on a deliberately disabled feature.
    failed_state = State(int(params.get("failed_endpoints_state", 0)))

    for name in reachable:
        yield Result(
            state=State.OK,
            notice=f"{_ENDPOINT_TITLES.get(name, name)}: reachable",
        )

    if failing:
        titles = ", ".join(_ENDPOINT_TITLES.get(n, n) for n in failing)
        yield Result(
            state=failed_state,
            summary=f"Not reachable or not enabled: {titles}",
        )

    yield Metric("n8n_api_endpoints_ok", len(reachable))
    yield Metric("n8n_api_endpoints_failed", len(failing))


agent_section_n8n_api_status = AgentSection(
    name="n8n_api_status",
    parse_function=parse_n8n_api_status,
)

check_plugin_n8n_api_status = CheckPlugin(
    name="n8n_api_status",
    sections=["n8n_api_status"],
    service_name="n8n API Endpoints",
    discovery_function=discover_n8n_api_status,
    check_function=check_n8n_api_status,
    check_ruleset_name="n8n_api_status",
    check_default_parameters={"failed_endpoints_state": 0},
)
