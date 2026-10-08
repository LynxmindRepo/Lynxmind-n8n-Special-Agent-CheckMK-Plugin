#!/usr/bin/env python3
"""
n8n GC Plugin for CheckMK
Monitors n8n garbage collection: alerts on the share of time spent in GC
and graphs the lifetime counters.
"""

import time
from typing import Any, Dict, Mapping, MutableMapping, Optional
from cmk.agent_based.v2 import (
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    GetRateError,
    IgnoreResultsError,
    Result,
    Service,
    State,
    Metric,
    check_levels,
    get_rate,
    get_value_store,
    render,
)

# Import the parsed section type from n8n_metrics
from .n8n_metrics import N8nMetricsInfo


GC_KINDS = ("minor", "major", "incremental")
GC_TOTAL = "gc_total"
GC_DURATION_SUM = "n8n_nodejs_gc_duration_seconds_sum_kind_{}"

# Mirrors the prefill of the ruleset.
DEFAULT_PARAMETERS = {"gc_time_percent": ("fixed", (5.0, 10.0))}


def _metric_key(metric_name: str) -> str:
    """Namespace a raw metric name, without doubling an existing ``n8n_``.

    The Prometheus names already start with ``n8n_``; blindly prefixing them
    produced metrics such as ``n8n_n8n_nodejs_gc_duration_...``.
    """
    return metric_name if metric_name.startswith("n8n_") else f"n8n_{metric_name}"


def _filter_gc_metrics(metrics: Dict) -> Dict:
    """Filter only the 4 most important GC metrics"""
    important_gc_metrics = [GC_TOTAL] + [GC_DURATION_SUM.format(kind) for kind in GC_KINDS]
    return {k: v for k, v in metrics.items() if k in important_gc_metrics}


def discover_n8n_gc(section: Optional[N8nMetricsInfo]) -> DiscoveryResult:
    """Discover n8n GC service"""
    if section is not None and section.get('available', False):
        metrics = section.get('metrics', {})
        filtered_metrics = _filter_gc_metrics(metrics)
        
        if filtered_metrics:
            yield Service()


def _gc_time_percent(
    lifetime_sums: Mapping[str, float],
    value_store: MutableMapping[str, Any],
    now: float,
) -> Dict[str, float]:
    """Share of wall-clock time spent in GC since the previous check, per kind.

    ``nodejs_gc_duration_seconds_sum`` is a counter: the seconds of GC
    accumulated since the n8n process started.  It only ever grows, so its
    absolute value says how long n8n has been running, not how busy the
    collector is.  The load is the growth between two checks.

    A kind is left out when it has no previous sample, or when its counter
    went backwards because n8n was restarted.
    """
    shares = {}
    for kind, seconds in lifetime_sums.items():
        try:
            rate = get_rate(
                value_store,
                f"gc_duration_seconds_sum.{kind}",
                now,
                seconds,
                raise_overflow=True,
            )
        except GetRateError:
            continue
        shares[kind] = rate * 100.0
    return shares


def check_n8n_gc(
    params: Mapping[str, Any],
    section: Optional[N8nMetricsInfo],
) -> CheckResult:
    """Check n8n GC metrics and generate graphs"""
    yield from check_n8n_gc_testable(params, section, get_value_store(), time.time())


def check_n8n_gc_testable(
    params: Mapping[str, Any],
    section: Optional[N8nMetricsInfo],
    value_store: MutableMapping[str, Any],
    now: float,
) -> CheckResult:
    """The check itself, with the value store and the clock passed in."""
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

    # Filter GC metrics, keep the numeric ones
    filtered_metrics = {
        name: float(value)
        for name, value in _filter_gc_metrics(metrics).items()
        if isinstance(value, (int, float))
    }

    if not filtered_metrics:
        yield Result(state=State.UNKNOWN, summary="No GC metrics available")
        return

    lifetime_sums = {
        kind: filtered_metrics[GC_DURATION_SUM.format(kind)]
        for kind in GC_KINDS
        if GC_DURATION_SUM.format(kind) in filtered_metrics
    }

    shares = _gc_time_percent(lifetime_sums, value_store, now)
    if lifetime_sums and not shares:
        # Raised only now, after every counter has been stored, so the next
        # check finds a baseline for all of them.
        raise IgnoreResultsError("Initializing GC counters (first check, or n8n was restarted)")

    if shares:
        # The only alerting signal: thresholds apply to the rate, never to
        # the lifetime sums below.
        yield from check_levels(
            sum(shares.values()),
            levels_upper=params.get("gc_time_percent"),
            metric_name="n8n_gc_time_percent",
            label="Time in GC",
            render_func=render.percent,
        )
        for kind, share in shares.items():
            yield Metric(f"n8n_gc_time_percent_{kind}", share)
        yield Result(
            state=State.OK,
            notice="By kind: " + ", ".join(
                f"{kind} {render.percent(share)}" for kind, share in shares.items()
            ),
        )

    # Lifetime counters: graphed for reference, deliberately without levels
    for metric_name, value in filtered_metrics.items():
        yield Metric(_metric_key(metric_name), value)

    details_parts = []
    if GC_TOTAL in filtered_metrics:
        details_parts.append(f"GC total: {filtered_metrics[GC_TOTAL]:.0f}")
    for kind, seconds in lifetime_sums.items():
        details_parts.append(f"GC {kind}: {seconds:.3f}s")

    if details_parts:
        yield Result(state=State.OK, notice="Since n8n start: " + " | ".join(details_parts))


# Register check plugin - uses n8n_metrics section and filters GC metrics
check_plugin_n8n_gc = CheckPlugin(
    name="n8n_gc_summary",
    sections=["n8n_metrics"],
    service_name="n8n GC",
    discovery_function=discover_n8n_gc,
    check_function=check_n8n_gc,
    check_ruleset_name="n8n_gc",
    check_default_parameters=DEFAULT_PARAMETERS,
)

