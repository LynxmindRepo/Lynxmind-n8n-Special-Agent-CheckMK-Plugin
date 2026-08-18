#!/usr/bin/env python3
"""
n8n Heap Graphing Plugin for CheckMK

Metric and graph definitions for the most important heap metrics
(overall usage plus the old/new heap spaces).

Note: the check plugin prefixes every metric name with 'n8n_', so:
  - 'heap_percent'                                     -> 'n8n_heap_percent'
  - 'heap_used'                                        -> 'n8n_heap_used'
  - 'n8n_nodejs_heap_space_size_total_bytes_space_*'   -> 'n8n_nodejs_heap_space_size_total_bytes_space_*'
    (the double prefix is intentional and must be kept)
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    IECNotation,
    Metric,
    StrictPrecision,
    Unit,
)

UNIT_PERCENT = Unit(DecimalNotation("%"), StrictPrecision(1))
UNIT_BYTES = Unit(IECNotation("B"))

# 1. Heap Usage % - Most important (has thresholds)
metric_n8n_heap_percent = Metric(
    name="n8n_heap_percent",
    title=Title("Heap Usage"),
    unit=UNIT_PERCENT,
    color=Color.ORANGE,
)

# 2. Heap Used - actual usage in bytes
metric_n8n_heap_used = Metric(
    name="n8n_heap_used",
    title=Title("Heap Used"),
    unit=UNIT_BYTES,
    color=Color.RED,
)

# 3. Old Space - long lived objects
metric_n8n_nodejs_heap_space_size_total_bytes_space_old = Metric(
    name="n8n_nodejs_heap_space_size_total_bytes_space_old",
    title=Title("Heap Space - Old"),
    unit=UNIT_BYTES,
    color=Color.BLUE,
)

# 4. New Space - new object allocations
metric_n8n_nodejs_heap_space_size_total_bytes_space_new = Metric(
    name="n8n_nodejs_heap_space_size_total_bytes_space_new",
    title=Title("Heap Space - New"),
    unit=UNIT_BYTES,
    color=Color.GREEN,
)

# Graph 1: Heap usage percentage (kept separate - different unit)
graph_n8n_heap_usage_percent = Graph(
    name="n8n_heap_usage_percent",
    title=Title("Heap Usage"),
    simple_lines=["n8n_heap_percent"],
)

# Graph 2: Heap used plus the individual spaces - all in bytes, so they
# are shown together.
graph_n8n_heap_bytes = Graph(
    name="n8n_heap_bytes",
    title=Title("Heap Used and Spaces"),
    simple_lines=[
        "n8n_heap_used",
        "n8n_nodejs_heap_space_size_total_bytes_space_old",
        "n8n_nodejs_heap_space_size_total_bytes_space_new",
    ],
)
