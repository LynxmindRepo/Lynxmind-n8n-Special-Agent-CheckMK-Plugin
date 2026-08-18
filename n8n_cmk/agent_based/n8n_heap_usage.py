#!/usr/bin/env python3
"""
n8n Heap Plugin for CheckMK
Monitors n8n heap metrics (usage + spaces)
Combines heap usage and heap spaces into a single unified plugin
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
from typing_extensions import TypedDict

# Import the parsed section type from n8n_metrics
from .n8n_metrics import N8nMetricsInfo


def _metric_key(metric_name: str) -> str:
    """Namespace a raw metric name, without doubling an existing ``n8n_``.

    The Prometheus names already start with ``n8n_``; blindly prefixing them
    produced metrics such as ``n8n_n8n_nodejs_gc_duration_...``.
    """
    return metric_name if metric_name.startswith("n8n_") else f"n8n_{metric_name}"


def _filter_heap_usage_metrics(metrics: Dict) -> Dict:
    """Filter only the most important heap metrics (usage + spaces)"""
    # Combine heap usage and heap spaces - only the most important metrics
    important_heap_metrics = [
        'heap_percent',  # Most important - with threshold
        'heap_used',     # Important - shows actual usage
        'n8n_nodejs_heap_space_size_total_bytes_space_old',  # Most important heap space
        'n8n_nodejs_heap_space_size_total_bytes_space_new',  # Important heap space
    ]
    return {k: v for k, v in metrics.items() if k in important_heap_metrics}


def discover_n8n_heap_usage(section: Optional[N8nMetricsInfo]) -> DiscoveryResult:
    """Discover n8n heap usage service"""
    if section is not None and section.get('available', False):
        metrics = section.get('metrics', {})
        filtered_metrics = _filter_heap_usage_metrics(metrics)
        
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


def check_n8n_heap_usage(
    params: Dict,
    section: Optional[N8nMetricsInfo],
) -> CheckResult:
    """Check n8n heap usage metrics"""
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

    # Filter heap usage metrics
    filtered_metrics = _filter_heap_usage_metrics(metrics)
    available_metrics = list(filtered_metrics.keys())

    if not available_metrics:
        yield Result(state=State.UNKNOWN, summary="No heap usage metrics available")
        return

    critical_metrics = []
    warning_metrics = []
    ok_metrics = []
    key_summary = []
    heap_percent_value = None
    heap_used_value = None
    old_space_value = None
    new_space_value = None

    # Helper function to extract levels from params
    def _extract_levels(param_value, default):
        return _normalize_levels(param_value, default)
    
    # Get thresholds from params, with defaults
    heap_percent_param = params.get('heap_percent')
    heap_used_param = params.get('heap_used')
    old_space_param = params.get('old_space')
    new_space_param = params.get('new_space')
    
    # Thresholds for all heap metrics.
    #
    # heap_percent is heap_used / heap_size_total, i.e. how full the heap V8
    # has *currently allocated* is - not how close the process is to its heap
    # limit.  V8 keeps that ratio high on purpose and only grows the heap when
    # it has to, so a healthy n8n sits at 80-95% for most of its life and the
    # old 80/90 defaults fired constantly.  prom-client does not export
    # nodejs_heap_size_limit_bytes, so the ratio cannot be rebased onto the
    # real ceiling here; instead it ships without levels and the absolute
    # heap_used below is what alerts by default.  Set levels in the ruleset if
    # you want the ratio watched anyway.
    thresholds = {
        'heap_percent': _extract_levels(heap_percent_param, None),
        'heap_used': _extract_levels(heap_used_param, (419430400, 524288000)),  # 400MB, 500MB
        'n8n_nodejs_heap_space_size_total_bytes_space_old': _extract_levels(old_space_param, (314572800, 419430400)),  # 300MB, 400MB
        'n8n_nodejs_heap_space_size_total_bytes_space_new': _extract_levels(new_space_param, (67108864, 134217728)),  # 64MB, 128MB
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

            # Handle main heap metrics for descriptive display and thresholds
            if metric_name == 'heap_percent':
                heap_percent_value = numeric_value
                if thresholds.get(metric_name):
                    try:
                        warn_threshold, crit_threshold = thresholds[metric_name]
                        if numeric_value > crit_threshold:
                            critical_metrics.append(f"{metric_name}: {numeric_value:.1f}%")
                        elif numeric_value > warn_threshold:
                            warning_metrics.append(f"{metric_name}: {numeric_value:.1f}%")
                        else:
                            ok_metrics.append(f"{metric_name}: {numeric_value:.1f}%")
                    except (ValueError, TypeError):
                        ok_metrics.append(f"{metric_name}: {numeric_value:.1f}%")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value:.1f}%")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'heap_used':
                heap_used_value = numeric_value
                if thresholds.get(metric_name):
                    try:
                        warn_threshold, crit_threshold = thresholds[metric_name]
                        if numeric_value > crit_threshold:
                            critical_metrics.append(f"{metric_name}: {numeric_value:.0f} bytes")
                        elif numeric_value > warn_threshold:
                            warning_metrics.append(f"{metric_name}: {numeric_value:.0f} bytes")
                        else:
                            ok_metrics.append(f"{metric_name}: {numeric_value:.0f} bytes")
                    except (ValueError, TypeError):
                        ok_metrics.append(f"{metric_name}: {numeric_value:.0f} bytes")
                else:
                    ok_metrics.append(f"{metric_name}: {numeric_value:.0f} bytes")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'n8n_nodejs_heap_space_size_total_bytes_space_old':
                old_space_value = numeric_value
                if thresholds.get(metric_name):
                    try:
                        warn_threshold, crit_threshold = thresholds[metric_name]
                        if numeric_value > crit_threshold:
                            critical_metrics.append(f"old_space: {numeric_value:.0f} bytes")
                        elif numeric_value > warn_threshold:
                            warning_metrics.append(f"old_space: {numeric_value:.0f} bytes")
                        else:
                            ok_metrics.append(f"old_space: {numeric_value:.0f} bytes")
                    except (ValueError, TypeError):
                        ok_metrics.append(f"old_space: {numeric_value:.0f} bytes")
                else:
                    ok_metrics.append(f"old_space: {numeric_value:.0f} bytes")
                # Don't add to key_summary, will be displayed separately
            elif metric_name == 'n8n_nodejs_heap_space_size_total_bytes_space_new':
                new_space_value = numeric_value
                if thresholds.get(metric_name):
                    try:
                        warn_threshold, crit_threshold = thresholds[metric_name]
                        if numeric_value > crit_threshold:
                            critical_metrics.append(f"new_space: {numeric_value:.0f} bytes")
                        elif numeric_value > warn_threshold:
                            warning_metrics.append(f"new_space: {numeric_value:.0f} bytes")
                        else:
                            ok_metrics.append(f"new_space: {numeric_value:.0f} bytes")
                    except (ValueError, TypeError):
                        ok_metrics.append(f"new_space: {numeric_value:.0f} bytes")
                else:
                    ok_metrics.append(f"new_space: {numeric_value:.0f} bytes")
                # Don't add to key_summary, will be displayed separately
            else:
                ok_metrics.append(f"{metric_name}: {numeric_value}")
                key_summary.append(f"{metric_name}: {numeric_value}")

        except (ValueError, TypeError):
            continue

    # Fallback: try to get values directly from metrics if not found in loop
    if heap_percent_value is None and 'heap_percent' in metrics:
        try:
            value = metrics['heap_percent']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                heap_percent_value = float(value)
            elif isinstance(value, (int, float)):
                heap_percent_value = float(value)
        except (ValueError, TypeError):
            pass
    
    if heap_used_value is None and 'heap_used' in metrics:
        try:
            value = metrics['heap_used']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                heap_used_value = float(value)
            elif isinstance(value, (int, float)):
                heap_used_value = float(value)
        except (ValueError, TypeError):
            pass
    
    if old_space_value is None and 'n8n_nodejs_heap_space_size_total_bytes_space_old' in metrics:
        try:
            value = metrics['n8n_nodejs_heap_space_size_total_bytes_space_old']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                old_space_value = float(value)
            elif isinstance(value, (int, float)):
                old_space_value = float(value)
        except (ValueError, TypeError):
            pass
    
    if new_space_value is None and 'n8n_nodejs_heap_space_size_total_bytes_space_new' in metrics:
        try:
            value = metrics['n8n_nodejs_heap_space_size_total_bytes_space_new']
            if isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit():
                new_space_value = float(value)
            elif isinstance(value, (int, float)):
                new_space_value = float(value)
        except (ValueError, TypeError):
            pass

    # Determine overall state
    if critical_metrics:
        overall_state = State.CRIT
    elif warning_metrics:
        overall_state = State.WARN
    else:
        overall_state = State.OK

    # Simple summary: show heap usage percentage
    if heap_percent_value is not None:
        summary = f"Heap {heap_percent_value:.1f}% of allocated heap"
    elif heap_used_value is not None:
        summary = f"Heap used {heap_used_value:.0f} bytes"
    else:
        summary = "Heap metrics available"

    yield Result(state=overall_state, summary=summary)

    # Build details with heap metrics first
    details_parts = []
    if heap_percent_value is not None:
        details_parts.append(f"Heap fill (used/allocated): {heap_percent_value:.1f}%")
    if heap_used_value is not None:
        details_parts.append(f"Heap used: {heap_used_value:.0f} bytes")
    if old_space_value is not None:
        details_parts.append(f"Old space: {old_space_value:.0f} bytes")
    if new_space_value is not None:
        details_parts.append(f"New space: {new_space_value:.0f} bytes")
    
    # Add other metrics (excluding the ones we already handled)
    filtered_key_summary = [
        item for item in key_summary 
        if not item.startswith('heap_percent') 
        and not item.startswith('heap_used')
        and not item.startswith('n8n_nodejs_heap_space_size_total_bytes_space_old')
        and not item.startswith('n8n_nodejs_heap_space_size_total_bytes_space_new')
    ]
    if filtered_key_summary:
        details_parts.extend(filtered_key_summary)
    
    if details_parts:
        yield Result(state=State.OK, notice=" | ".join(details_parts[:5]))


# Register check plugin - uses n8n_metrics section and filters heap metrics (usage + spaces)
check_plugin_n8n_heap_usage = CheckPlugin(
    name="n8n_heap_usage",
    sections=["n8n_metrics"],
    service_name="n8n Heap",
    discovery_function=discover_n8n_heap_usage,
    check_function=check_n8n_heap_usage,
    check_ruleset_name="n8n_heap_usage",
    check_default_parameters={},
)


