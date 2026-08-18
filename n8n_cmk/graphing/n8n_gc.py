#!/usr/bin/env python3
"""
n8n GC Graphing Plugin for CheckMK

Metric and graph definitions for the 4 most important GC metrics:
total, minor, major and incremental.

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
