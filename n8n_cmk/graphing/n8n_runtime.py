#!/usr/bin/env python3
"""
n8n Runtime Graphing Plugin for CheckMK

Metric and graph definitions for the Node.js runtime metrics:
file descriptors, event loop lag, active handles and active resources.

Note: the check plugin prefixes every metric name with 'n8n_', so metrics
that are already called 'n8n_*' upstream end up with a double prefix
('n8n_process_max_fds').  That is what the check actually sends, so the
names below must keep it.
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

# --- File descriptors --------------------------------------------------------
metric_n8n_fds = Metric(
    name="n8n_fds",
    title=Title("File Descriptors"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_n8n_process_max_fds = Metric(
    name="n8n_process_max_fds",
    title=Title("Max File Descriptors"),
    unit=UNIT_COUNT,
    color=Color.DARK_ORANGE,
)

# --- Event loop lag ----------------------------------------------------------
metric_n8n_eventloop_lag = Metric(
    name="n8n_eventloop_lag",
    title=Title("Event Loop Lag"),
    unit=UNIT_TIME,
    color=Color.ORANGE,
)

metric_n8n_eventloop_lag_ms = Metric(
    name="n8n_eventloop_lag_ms",
    title=Title("Event Loop Lag (ms)"),
    unit=UNIT_TIME,
    color=Color.LIGHT_ORANGE,
)

metric_n8n_nodejs_eventloop_lag_mean_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_mean_seconds",
    title=Title("Event Loop Lag Mean"),
    unit=UNIT_TIME,
    color=Color.RED,
)

metric_n8n_nodejs_eventloop_lag_max_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_max_seconds",
    title=Title("Event Loop Lag Max"),
    unit=UNIT_TIME,
    color=Color.DARK_RED,
)

metric_n8n_nodejs_eventloop_lag_min_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_min_seconds",
    title=Title("Event Loop Lag Min"),
    unit=UNIT_TIME,
    color=Color.LIGHT_YELLOW,
)

metric_n8n_nodejs_eventloop_lag_p50_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_p50_seconds",
    title=Title("Event Loop Lag P50"),
    unit=UNIT_TIME,
    color=Color.YELLOW,
)

metric_n8n_nodejs_eventloop_lag_p90_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_p90_seconds",
    title=Title("Event Loop Lag P90"),
    unit=UNIT_TIME,
    color=Color.BROWN,
)

metric_n8n_nodejs_eventloop_lag_p99_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_p99_seconds",
    title=Title("Event Loop Lag P99"),
    unit=UNIT_TIME,
    color=Color.DARK_BROWN,
)

metric_n8n_nodejs_eventloop_lag_stddev_seconds = Metric(
    name="n8n_nodejs_eventloop_lag_stddev_seconds",
    title=Title("Event Loop Lag StdDev"),
    unit=UNIT_TIME,
    color=Color.LIGHT_BROWN,
)

# --- Active handles ----------------------------------------------------------
metric_n8n_active_handles = Metric(
    name="n8n_active_handles",
    title=Title("Active Handles"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_n8n_nodejs_active_handles_type_ChildProcess = Metric(
    name="n8n_nodejs_active_handles_type_ChildProcess",
    title=Title("Active Handles - ChildProcess"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_GREEN,
)

metric_n8n_nodejs_active_handles_type_Server = Metric(
    name="n8n_nodejs_active_handles_type_Server",
    title=Title("Active Handles - Server"),
    unit=UNIT_COUNT,
    color=Color.DARK_GREEN,
)

metric_n8n_nodejs_active_handles_type_Socket = Metric(
    name="n8n_nodejs_active_handles_type_Socket",
    title=Title("Active Handles - Socket"),
    unit=UNIT_COUNT,
    color=Color.CYAN,
)

# --- Active resources --------------------------------------------------------
metric_n8n_active_resources = Metric(
    name="n8n_active_resources",
    title=Title("Active Resources"),
    unit=UNIT_COUNT,
    color=Color.PINK,
)

metric_n8n_nodejs_active_resources_type_Immediate = Metric(
    name="n8n_nodejs_active_resources_type_Immediate",
    title=Title("Active Resources - Immediate"),
    unit=UNIT_COUNT,
    color=Color.DARK_PINK,
)

metric_n8n_nodejs_active_resources_type_PipeWrap = Metric(
    name="n8n_nodejs_active_resources_type_PipeWrap",
    title=Title("Active Resources - PipeWrap"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_PINK,
)

metric_n8n_nodejs_active_resources_type_ProcessWrap = Metric(
    name="n8n_nodejs_active_resources_type_ProcessWrap",
    title=Title("Active Resources - ProcessWrap"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_RED,
)

metric_n8n_nodejs_active_resources_type_TCPServerWrap = Metric(
    name="n8n_nodejs_active_resources_type_TCPServerWrap",
    title=Title("Active Resources - TCPServerWrap"),
    unit=UNIT_COUNT,
    color=Color.PURPLE,
)

metric_n8n_nodejs_active_resources_type_TCPSocketWrap = Metric(
    name="n8n_nodejs_active_resources_type_TCPSocketWrap",
    title=Title("Active Resources - TCPSocketWrap"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_PURPLE,
)

metric_n8n_nodejs_active_resources_type_Timeout = Metric(
    name="n8n_nodejs_active_resources_type_Timeout",
    title=Title("Active Resources - Timeout"),
    unit=UNIT_COUNT,
    color=Color.DARK_PURPLE,
)

# --- Graphs ------------------------------------------------------------------
# File descriptors: current against the process maximum.
graph_n8n_file_descriptors = Graph(
    name="n8n_file_descriptors",
    title=Title("n8n File Descriptors"),
    simple_lines=["n8n_fds", "n8n_process_max_fds"],
)

# Event loop lag: everything in seconds.  The individual percentiles are
# optional because not every n8n build exposes them.
graph_n8n_eventloop_lag = Graph(
    name="n8n_eventloop_lag",
    title=Title("n8n Event Loop Lag"),
    simple_lines=[
        "n8n_eventloop_lag",
        "n8n_eventloop_lag_ms",
        "n8n_nodejs_eventloop_lag_min_seconds",
        "n8n_nodejs_eventloop_lag_mean_seconds",
        "n8n_nodejs_eventloop_lag_max_seconds",
        "n8n_nodejs_eventloop_lag_p50_seconds",
        "n8n_nodejs_eventloop_lag_p90_seconds",
        "n8n_nodejs_eventloop_lag_p99_seconds",
        "n8n_nodejs_eventloop_lag_stddev_seconds",
    ],
    optional=[
        "n8n_eventloop_lag",
        "n8n_eventloop_lag_ms",
        "n8n_nodejs_eventloop_lag_min_seconds",
        "n8n_nodejs_eventloop_lag_max_seconds",
        "n8n_nodejs_eventloop_lag_p50_seconds",
        "n8n_nodejs_eventloop_lag_p90_seconds",
        "n8n_nodejs_eventloop_lag_p99_seconds",
        "n8n_nodejs_eventloop_lag_stddev_seconds",
    ],
)

# Active handles: total plus the breakdown by type.
graph_n8n_active_handles = Graph(
    name="n8n_active_handles",
    title=Title("n8n Active Handles"),
    simple_lines=[
        "n8n_active_handles",
        "n8n_nodejs_active_handles_type_ChildProcess",
        "n8n_nodejs_active_handles_type_Server",
        "n8n_nodejs_active_handles_type_Socket",
    ],
    optional=[
        "n8n_nodejs_active_handles_type_ChildProcess",
        "n8n_nodejs_active_handles_type_Server",
        "n8n_nodejs_active_handles_type_Socket",
    ],
)

# Active resources: total plus the breakdown by type.
graph_n8n_active_resources = Graph(
    name="n8n_active_resources",
    title=Title("n8n Active Resources"),
    simple_lines=[
        "n8n_active_resources",
        "n8n_nodejs_active_resources_type_Immediate",
        "n8n_nodejs_active_resources_type_PipeWrap",
        "n8n_nodejs_active_resources_type_ProcessWrap",
        "n8n_nodejs_active_resources_type_TCPServerWrap",
        "n8n_nodejs_active_resources_type_TCPSocketWrap",
        "n8n_nodejs_active_resources_type_Timeout",
    ],
    optional=[
        "n8n_nodejs_active_resources_type_Immediate",
        "n8n_nodejs_active_resources_type_PipeWrap",
        "n8n_nodejs_active_resources_type_ProcessWrap",
        "n8n_nodejs_active_resources_type_TCPServerWrap",
        "n8n_nodejs_active_resources_type_TCPSocketWrap",
        "n8n_nodejs_active_resources_type_Timeout",
    ],
)
