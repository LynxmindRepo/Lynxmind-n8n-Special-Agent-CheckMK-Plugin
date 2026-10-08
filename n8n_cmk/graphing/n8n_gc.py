#!/usr/bin/env python3
"""
n8n GC Graphing Plugin for CheckMK

Metric and graph definitions for the time spent in GC (total and by kind)
and for the 4 lifetime counters: total, minor, major and incremental.

Note: the check plugin prefixes every metric name with 'n8n_', so:
  - 'gc_total'                                  -> 'n8n_gc_total'
  - 'n8n_nodejs_gc_duration_seconds_sum_kind_*' -> 'n8n_nodejs_gc_duration_seconds_sum_kind_*'
    (the double prefix is intentional and must be kept, it is what the
    check actually sends)
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    Metric,
    StrictPrecision,
    TimeNotation,
    Unit,
)

UNIT_COUNT = Unit(DecimalNotation(""), StrictPrecision(0))
UNIT_TIME = Unit(TimeNotation())
# No fixed precision: a healthy instance sits at a few hundredths of a percent.
UNIT_PERCENT = Unit(DecimalNotation("%"))

# Share of wall-clock time spent in GC since the previous check. This is the
# metric the service alerts on; the sums below are lifetime counters.
metric_n8n_gc_time_percent = Metric(
    name="n8n_gc_time_percent",
    title=Title("Time in GC"),
    unit=UNIT_PERCENT,
    color=Color.ORANGE,
)

metric_n8n_gc_time_percent_minor = Metric(
    name="n8n_gc_time_percent_minor",
    title=Title("Time in GC - Minor"),
    unit=UNIT_PERCENT,
    color=Color.GREEN,
)

metric_n8n_gc_time_percent_major = Metric(
    name="n8n_gc_time_percent_major",
    title=Title("Time in GC - Major"),
    unit=UNIT_PERCENT,
    color=Color.RED,
)

metric_n8n_gc_time_percent_incremental = Metric(
    name="n8n_gc_time_percent_incremental",
    title=Title("Time in GC - Incremental"),
    unit=UNIT_PERCENT,
    color=Color.BLUE,
)

# The kinds add up to the total, so they are stacked.
graph_n8n_gc_time_by_kind = Graph(
    name="n8n_gc_time_by_kind",
    title=Title("Time in GC by kind"),
    compound_lines=[
        "n8n_gc_time_percent_minor",
        "n8n_gc_time_percent_major",
        "n8n_gc_time_percent_incremental",
    ],
)

# 1. GC Total - Total number of garbage collections
metric_n8n_gc_total = Metric(
    name="n8n_gc_total",
    title=Title("GC Total"),
    unit=UNIT_COUNT,
    color=Color.ORANGE,
)

# 2. GC Duration Sum - Minor (most frequent, less impactful)
metric_n8n_nodejs_gc_duration_seconds_sum_kind_minor = Metric(
    name="n8n_nodejs_gc_duration_seconds_sum_kind_minor",
    title=Title("GC Duration Sum - Minor"),
    unit=UNIT_TIME,
    color=Color.GREEN,
)

# 3. GC Duration Sum - Major (less frequent, more impactful)
metric_n8n_nodejs_gc_duration_seconds_sum_kind_major = Metric(
    name="n8n_nodejs_gc_duration_seconds_sum_kind_major",
    title=Title("GC Duration Sum - Major"),
    unit=UNIT_TIME,
    color=Color.RED,
)

# 4. GC Duration Sum - Incremental
metric_n8n_nodejs_gc_duration_seconds_sum_kind_incremental = Metric(
    name="n8n_nodejs_gc_duration_seconds_sum_kind_incremental",
    title=Title("GC Duration Sum - Incremental"),
    unit=UNIT_TIME,
    color=Color.BLUE,
)

# Graph 1: GC Total
graph_n8n_gc_total = Graph(
    name="n8n_gc_total",
    title=Title("GC Total"),
    simple_lines=["n8n_gc_total"],
)

# Graph 2: GC duration by kind - the three durations share the same unit,
# so they are shown together for comparison.
graph_n8n_gc_duration = Graph(
    name="n8n_gc_duration",
    title=Title("GC Duration"),
    simple_lines=[
        "n8n_nodejs_gc_duration_seconds_sum_kind_minor",
        "n8n_nodejs_gc_duration_seconds_sum_kind_major",
        "n8n_nodejs_gc_duration_seconds_sum_kind_incremental",
    ],
)
