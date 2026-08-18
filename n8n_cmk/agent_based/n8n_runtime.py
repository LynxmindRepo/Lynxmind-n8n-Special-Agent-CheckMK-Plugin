#!/usr/bin/env python3
"""
n8n Runtime Plugin for CheckMK
Monitors n8n runtime metrics (file descriptors, eventloop, handles, resources)
"""

from typing import Dict, Optional
from cmk.agent_based.v2 import (
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    Metric,
)

# Import the parsed section type from n8n_metrics
from .n8n_metrics import N8nMetricsInfo


def _metric_key(metric_name: str) -> str:
    """Namespace a raw metric name, without doubling an existing ``n8n_``.

    The Prometheus names already start with ``n8n_``; blindly prefixing them
    produced metrics such as ``n8n_n8n_nodejs_gc_duration_...``.
    """
    return metric_name if metric_name.startswith("n8n_") else f"n8n_{metric_name}"


def _filter_runtime_metrics(metrics: Dict) -> Dict:
    """Filter only the 4 most important runtime metrics"""
    # Only collect the 4 most important runtime metrics for graphs
    important_runtime_metrics = [
        'fds',
        'eventloop_lag_ms',
        'active_handles',
        'active_resources',
    ]
    return {k: v for k, v in metrics.items() if k in important_runtime_metrics}


def discover_n8n_runtime(section: Optional[N8nMetricsInfo]) -> DiscoveryResult:
    """Discover n8n runtime service"""
    if section is not None and section.get('available', False):
        metrics = section.get('metrics', {})
        filtered_metrics = _filter_runtime_metrics(metrics)
        
        if filtered_metrics:
            yield Service()


def _normalize_levels(param_value, default):
    """Return a plain ``(warn, crit)`` tuple for any threshold parameter shape.

    Rulesets built with ``SimpleLevels`` hand the check a two element tuple
    ``("fixed", (warn, crit))`` or ``("no_levels", None)``.  Unpacking that
    directly yields the string/tuple pair instead of the numbers and every
    later comparison raises ``TypeError``.  Accepted shapes:

      * ``None``                     -> ``default``
      * ``("no_levels", None)``      -> ``None`` (levels switched off)
      * ``("fixed", (warn, crit))``  -> ``(warn, crit)``
      * ``{"levels_upper": ...}``    -> normalized inner value
      * ``(warn, crit)``             -> ``(warn, crit)`` (legacy/plain tuple)
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


def check_n8n_runtime(
    params: Dict,
    section: Optional[N8nMetricsInfo],
) -> CheckResult:
    """Check n8n runtime metrics"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No metrics data available")
        return

    if not section.get('available', False):
        if 'error' in section:
            yield Result(
                state=State.CRIT,
                summary=f"Metrics collection failed: {section['error']}"
            )
        else:
            yield Result(
                state=State.WARN,
                summary="Metrics endpoint not available"
            )
        return

    metrics = section.get('metrics', {})
    if not metrics:
        yield Result(state=State.UNKNOWN, summary="No metrics found")
        return

    # Filter runtime metrics
    filtered_metrics = _filter_runtime_metrics(metrics)
    available_metrics = list(filtered_metrics.keys())

    if not available_metrics:
        yield Result(state=State.UNKNOWN, summary="No runtime metrics available")
        return

    critical_metrics = []
    warning_metrics = []
    ok_metrics = []
    key_summary = []
    fds_value = None
    eventloop_lag_ms_value = None
    active_handles_value = None
    active_resources_value = None

    # Get thresholds from params, with defaults
    # SimpleLevels returns parameters in a specific format
    # Handle both dict format and tuple format
    def _extract_levels(param_value, default):
        return _normalize_levels(param_value, default)
    
    fds_param = params.get('fds')
    eventloop_lag_ms_param = params.get('eventloop_lag_ms')
    active_handles_param = params.get('active_handles')
    active_resources_param = params.get('active_resources')
    
    # Thresholds for the 4 most important runtime metrics
    # fds: File descriptors - warning at 400, critical at 700 (typical limit is 1024)
    fds_levels = _extract_levels(fds_param, (400, 700))
    # eventloop_lag_ms: Event loop lag in milliseconds - warning at 10ms, critical at 50ms (Node.js performance)
    eventloop_lag_ms_levels = _extract_levels(eventloop_lag_ms_param, (10.0, 50.0))
    # active_handles: Active handles - warning at 50, critical at 100
    active_handles_levels = _extract_levels(active_handles_param, (50, 100))
    # active_resources: Active resources - warning at 100, critical at 200
    active_resources_levels = _extract_levels(active_resources_param, (100, 200))
    
    thresholds = {
        'fds': fds_levels,
        'eventloop_lag_ms': eventloop_lag_ms_levels,
        'active_handles': active_handles_levels,
        'active_resources': active_resources_levels
    }

    for metric_name in available_metrics:
        value = filtered_metrics[metric_name]
        metric_key = _metric_key(metric_name)

        try:
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                numeric_value = float(value)
            elif isinstance(value, (int, float)):
                numeric_value = float(value)
            else:
                key_summary.append(f"{metric_name}: {value}")
                continue

            yield Metric(metric_key, numeric_value, levels=thresholds.get(metric_name))

            # Handle main runtime metrics for descriptive display
            if metric_name == 'fds':
                fds_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"{metric_name}: {numeric_value}")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"{metric_name}: {numeric_value}")
                    else:
                        ok_metrics.append(f"{metric_name}: {numeric_value}")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value}")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'eventloop_lag_ms':
                eventloop_lag_ms_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"{metric_name}: {numeric_value}")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"{metric_name}: {numeric_value}")
                    else:
                        ok_metrics.append(f"{metric_name}: {numeric_value}")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value}")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'active_handles':
                active_handles_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"{metric_name}: {numeric_value}")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"{metric_name}: {numeric_value}")
                    else:
                        ok_metrics.append(f"{metric_name}: {numeric_value}")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value}")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'active_resources':
                active_resources_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"{metric_name}: {numeric_value}")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"{metric_name}: {numeric_value}")
                    else:
                        ok_metrics.append(f"{metric_name}: {numeric_value}")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value}")
                # Don't add to key_summary, will be displayed separately
            else:
                ok_metrics.append(f"{metric_name}: {numeric_value}")
                if metric_name in ['eventloop_lag_ms']:
                    key_summary.append(f"{metric_name}: {numeric_value:.2f} ms")
                elif 'seconds' in metric_name:
                    key_summary.append(f"{metric_name}: {numeric_value:.3f}s")
                else:
                    key_summary.append(f"{metric_name}: {numeric_value}")

        except (ValueError, TypeError):
            continue

    # Fallback: try to get values directly from metrics if not found in loop
    if fds_value is None and 'fds' in metrics:
        try:
            value = metrics['fds']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                fds_value = float(value)
            elif isinstance(value, (int, float)):
                fds_value = float(value)
        except (ValueError, TypeError):
            pass
    
    if eventloop_lag_ms_value is None and 'eventloop_lag_ms' in metrics:
        try:
            value = metrics['eventloop_lag_ms']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                eventloop_lag_ms_value = float(value)
            elif isinstance(value, (int, float)):
                eventloop_lag_ms_value = float(value)
        except (ValueError, TypeError):
            pass

    # Determine overall state
    if critical_metrics:
        overall_state = State.CRIT
    elif warning_metrics:
        overall_state = State.WARN
    else:
        overall_state = State.OK

    # Summary: show status message
    if overall_state == State.OK:
        summary = "All core Runtime metrics OK"
    elif critical_metrics:
        summary = ", ".join(critical_metrics[:2])  # Show first 2 critical issues
        if len(critical_metrics) > 2:
            summary += f" (+{len(critical_metrics) - 2} more)"
    elif warning_metrics:
        summary = ", ".join(warning_metrics[:2])  # Show first 2 warnings
        if len(warning_metrics) > 2:
            summary += f" (+{len(warning_metrics) - 2} more)"
    else:
        summary = "Runtime metrics available"

    yield Result(state=overall_state, summary=summary)

    # Build details with main runtime metrics first
    details_parts = []
    if fds_value is not None:
        details_parts.append(f"File descriptors: {fds_value:.0f}")
    if eventloop_lag_ms_value is not None:
        details_parts.append(f"Event loop lag: {eventloop_lag_ms_value:.2f} ms")
    if active_handles_value is not None:
        details_parts.append(f"Active handles: {active_handles_value:.0f}")
    if active_resources_value is not None:
        details_parts.append(f"Active resources: {active_resources_value:.0f}")
    
    # Add other metrics (excluding the ones we already handled)
    filtered_key_summary = [
        m for m in key_summary 
        if not m.startswith('fds:') 
        and not m.startswith('eventloop_lag_ms:')
        and not m.startswith('active_handles:')
        and not m.startswith('active_resources:')
    ]
    if filtered_key_summary:
        details_parts.extend(filtered_key_summary)
    
    if details_parts:
        yield Result(state=State.OK, notice=" | ".join(details_parts[:5]))


# Register check plugin - uses n8n_metrics section and filters runtime metrics
check_plugin_n8n_runtime = CheckPlugin(
    name="n8n_runtime",
    sections=["n8n_metrics"],
    service_name="n8n Runtime",
    discovery_function=discover_n8n_runtime,
    check_function=check_n8n_runtime,
    check_ruleset_name="n8n_runtime",
    check_default_parameters={},
)

