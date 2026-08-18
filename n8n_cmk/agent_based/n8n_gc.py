#!/usr/bin/env python3
"""
n8n GC Plugin for CheckMK
Monitors n8n garbage collection metrics and generates 4 graphs
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


def _filter_gc_metrics(metrics: Dict) -> Dict:
    """Filter only the 4 most important GC metrics"""
    important_gc_metrics = [
        'gc_total',
        'n8n_nodejs_gc_duration_seconds_sum_kind_minor',
        'n8n_nodejs_gc_duration_seconds_sum_kind_major',
        'n8n_nodejs_gc_duration_seconds_sum_kind_incremental',
    ]
    return {k: v for k, v in metrics.items() if k in important_gc_metrics}


def discover_n8n_gc(section: Optional[N8nMetricsInfo]) -> DiscoveryResult:
    """Discover n8n GC service"""
    if section is not None and section.get('available', False):
        metrics = section.get('metrics', {})
        filtered_metrics = _filter_gc_metrics(metrics)
        
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


def check_n8n_gc(
    params: Dict,
    section: Optional[N8nMetricsInfo],
) -> CheckResult:
    """Check n8n GC metrics and generate graphs"""
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

    # Filter GC metrics
    filtered_metrics = _filter_gc_metrics(metrics)
    available_metrics = list(filtered_metrics.keys())

    if not available_metrics:
        yield Result(state=State.UNKNOWN, summary="No GC metrics available")
        return

    critical_metrics = []
    warning_metrics = []
    gc_total_value = None
    gc_minor_value = None
    gc_major_value = None
    gc_incremental_value = None

    # Get thresholds from params, with defaults
    def _extract_levels(param_value, default):
        return _normalize_levels(param_value, default)
    
    gc_duration_param = params.get('gc_duration_seconds')
    gc_duration_levels = _extract_levels(gc_duration_param, (1.0, 5.0))
    
    thresholds = {
        'n8n_nodejs_gc_duration_seconds_sum_kind_minor': gc_duration_levels,
        'n8n_nodejs_gc_duration_seconds_sum_kind_major': gc_duration_levels,
        'n8n_nodejs_gc_duration_seconds_sum_kind_incremental': gc_duration_levels,
    }

    # Process each metric
    for metric_name in available_metrics:
        if metric_name not in ['gc_total', 'n8n_nodejs_gc_duration_seconds_sum_kind_minor', 
                               'n8n_nodejs_gc_duration_seconds_sum_kind_major', 
                               'n8n_nodejs_gc_duration_seconds_sum_kind_incremental']:
            continue
            
        value = filtered_metrics[metric_name]

        try:
            # Convert to numeric value
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                numeric_value = float(value)
            elif isinstance(value, (int, float)):
                numeric_value = float(value)
            else:
                continue

            # Emit metric for graph generation (CheckMK adds 'n8n_' prefix automatically)
            metric_key = _metric_key(metric_name)
            yield Metric(metric_key, numeric_value, levels=thresholds.get(metric_name))

            # Check thresholds and collect values
            if metric_name == 'gc_total':
                gc_total_value = numeric_value
            elif metric_name == 'n8n_nodejs_gc_duration_seconds_sum_kind_minor':
                gc_minor_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"GC minor: {numeric_value:.3f}s")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"GC minor: {numeric_value:.3f}s")
            elif metric_name == 'n8n_nodejs_gc_duration_seconds_sum_kind_major':
                gc_major_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"GC major: {numeric_value:.3f}s")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"GC major: {numeric_value:.3f}s")
            elif metric_name == 'n8n_nodejs_gc_duration_seconds_sum_kind_incremental':
                gc_incremental_value = numeric_value
                if thresholds.get(metric_name):
                    warn_threshold, crit_threshold = thresholds[metric_name]
                    if numeric_value > crit_threshold:
                        critical_metrics.append(f"GC incremental: {numeric_value:.3f}s")
                    elif numeric_value > warn_threshold:
                        warning_metrics.append(f"GC incremental: {numeric_value:.3f}s")

        except (ValueError, TypeError):
            continue

    # Determine overall state
    if critical_metrics:
        overall_state = State.CRIT
    elif warning_metrics:
        overall_state = State.WARN
    else:
        overall_state = State.OK

    # Summary: show status message
    if overall_state == State.OK:
        summary = "All core GC metrics OK"
    elif critical_metrics:
        summary = ", ".join(critical_metrics[:2])  # Show first 2 critical issues
        if len(critical_metrics) > 2:
            summary += f" (+{len(critical_metrics) - 2} more)"
    elif warning_metrics:
        summary = ", ".join(warning_metrics[:2])  # Show first 2 warnings
        if len(warning_metrics) > 2:
            summary += f" (+{len(warning_metrics) - 2} more)"
    else:
        summary = "GC metrics available"

    yield Result(state=overall_state, summary=summary)

    # Build details
    details_parts = []
    if gc_total_value is not None:
        details_parts.append(f"GC total: {gc_total_value:.0f}")
    if gc_minor_value is not None:
        details_parts.append(f"GC minor: {gc_minor_value:.3f}s")
    if gc_major_value is not None:
        details_parts.append(f"GC major: {gc_major_value:.3f}s")
    if gc_incremental_value is not None:
        details_parts.append(f"GC incremental: {gc_incremental_value:.3f}s")
    
    if details_parts:
        yield Result(state=State.OK, notice=" | ".join(details_parts))


# Register check plugin - uses n8n_metrics section and filters GC metrics
check_plugin_n8n_gc = CheckPlugin(
    name="n8n_gc_summary",
    sections=["n8n_metrics"],
    service_name="n8n GC",
    discovery_function=discover_n8n_gc,
    check_function=check_n8n_gc,
    check_ruleset_name="n8n_gc",
    check_default_parameters={},
)

