#!/usr/bin/env python3
"""
n8n Workflows Graphing Plugin for CheckMK

Metric and graph definitions for both the overall workflow statistics
service ('n8n Workflows') and the per workflow services ('n8n Workflow <name>').
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph, MinimalRange
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    Metric,
    StrictPrecision,
    TimeNotation,
    Unit,
)
from cmk.graphing.v1.perfometers import Closed, FocusRange, Perfometer

UNIT_COUNT = Unit(DecimalNotation(""), StrictPrecision(0))
UNIT_PERCENT = Unit(DecimalNotation("%"), StrictPrecision(1))
UNIT_TIME = Unit(TimeNotation())

# --- Overall workflow statistics ---------------------------------------------
metric_n8n_workflows_total = Metric(
    name="n8n_workflows_total",
    title=Title("Total Workflows"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_n8n_workflows_active = Metric(
    name="n8n_workflows_active",
    title=Title("Active Workflows"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_n8n_workflows_inactive = Metric(
    name="n8n_workflows_inactive",
    title=Title("Inactive Workflows"),
    unit=UNIT_COUNT,
    color=Color.DARK_ORANGE,
)

metric_n8n_workflows_active_percent = Metric(
    name="n8n_workflows_active_percent",
    title=Title("Active Workflows"),
    unit=UNIT_PERCENT,
    color=Color.ORANGE,
)

metric_n8n_workflows_recently_updated = Metric(
    name="n8n_workflows_recently_updated",
    title=Title("Recently Updated"),
    unit=UNIT_COUNT,
    color=Color.PINK,
)

metric_n8n_workflows_with_tags = Metric(
    name="n8n_workflows_with_tags",
    title=Title("Workflows with Tags"),
    unit=UNIT_COUNT,
    color=Color.CYAN,
)

metric_n8n_workflows_without_tags = Metric(
    name="n8n_workflows_without_tags",
    title=Title("Workflows without Tags"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_BROWN,
)

metric_n8n_workflows_tagged_percent = Metric(
    name="n8n_workflows_tagged_percent",
    title=Title("Tagged Workflows"),
    unit=UNIT_PERCENT,
    color=Color.LIGHT_ORANGE,
)

metric_n8n_workflows_avg_nodes = Metric(
    name="n8n_workflows_avg_nodes",
    title=Title("Average Nodes"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_n8n_workflows_avg_connections = Metric(
    name="n8n_workflows_avg_connections",
    title=Title("Average Connections"),
    unit=UNIT_COUNT,
    color=Color.PURPLE,
)

# --- Individual workflow: structure ------------------------------------------
metric_workflow_nodes = Metric(
    name="workflow_nodes",
    title=Title("Nodes"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_workflow_connections = Metric(
    name="workflow_connections",
    title=Title("Connections"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_workflow_complexity = Metric(
    name="workflow_complexity",
    title=Title("Complexity"),
    unit=UNIT_COUNT,
    color=Color.DARK_ORANGE,
)

metric_workflow_active = Metric(
    name="workflow_active",
    title=Title("Active"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

# --- Individual workflow: executions (all time) ------------------------------
metric_workflow_total_executions = Metric(
    name="workflow_total_executions",
    title=Title("Total Executions"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_workflow_successful_executions = Metric(
    name="workflow_successful_executions",
    title=Title("Successful Executions"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_workflow_failed_executions = Metric(
    name="workflow_failed_executions",
    title=Title("Failed Executions"),
    unit=UNIT_COUNT,
    color=Color.RED,
)

metric_workflow_success_rate = Metric(
    name="workflow_success_rate",
    title=Title("Success Rate"),
    unit=UNIT_PERCENT,
    color=Color.ORANGE,
)

# --- Individual workflow: 24h ------------------------------------------------
metric_workflow_total_executions_24h = Metric(
    name="workflow_total_executions_24h",
    title=Title("Total Executions (24h)"),
    unit=UNIT_COUNT,
    color=Color.BLUE,
)

metric_workflow_successful_executions_24h = Metric(
    name="workflow_successful_executions_24h",
    title=Title("Successful Executions (24h)"),
    unit=UNIT_COUNT,
    color=Color.GREEN,
)

metric_workflow_failed_executions_24h = Metric(
    name="workflow_failed_executions_24h",
    title=Title("Failed Executions (24h)"),
    unit=UNIT_COUNT,
    color=Color.RED,
)

metric_workflow_success_rate_24h = Metric(
    name="workflow_success_rate_24h",
    title=Title("Success Rate (24h)"),
    unit=UNIT_PERCENT,
    color=Color.LIGHT_ORANGE,
)

# --- Individual workflow: 8h -------------------------------------------------
metric_workflow_total_executions_8h = Metric(
    name="workflow_total_executions_8h",
    title=Title("Total Executions (8h)"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_BLUE,
)

metric_workflow_successful_executions_8h = Metric(
    name="workflow_successful_executions_8h",
    title=Title("Successful Executions (8h)"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_GREEN,
)

metric_workflow_failed_executions_8h = Metric(
    name="workflow_failed_executions_8h",
    title=Title("Failed Executions (8h)"),
    unit=UNIT_COUNT,
    color=Color.LIGHT_RED,
)

metric_workflow_success_rate_8h = Metric(
    name="workflow_success_rate_8h",
    title=Title("Success Rate (8h)"),
    unit=UNIT_PERCENT,
    color=Color.YELLOW,
)

# --- Individual workflow: failure analysis -----------------------------------
metric_workflow_avg_failure_duration = Metric(
    name="workflow_avg_failure_duration",
    title=Title("Avg Failure Duration"),
    unit=UNIT_TIME,
    color=Color.DARK_ORANGE,
)

metric_workflow_failure_duration_p95 = Metric(
    name="workflow_failure_duration_p95",
    title=Title("Failure Duration P95"),
    unit=UNIT_TIME,
    color=Color.RED,
)

metric_workflow_failure_duration_p99 = Metric(
    name="workflow_failure_duration_p99",
    title=Title("Failure Duration P99"),
    unit=UNIT_TIME,
    color=Color.DARK_RED,
)

metric_workflow_recent_failures_count = Metric(
    name="workflow_recent_failures_count",
    title=Title("Recent Failures Count"),
    unit=UNIT_COUNT,
    color=Color.DARK_PINK,
)

# --- Graphs: overall statistics ----------------------------------------------
graph_n8n_workflows_counts = Graph(
    name="n8n_workflows_counts",
    title=Title("n8n Workflows"),
    compound_lines=["n8n_workflows_active", "n8n_workflows_inactive"],
    simple_lines=[
        "n8n_workflows_total",
        "n8n_workflows_recently_updated",
        "n8n_workflows_with_tags",
        "n8n_workflows_without_tags",
    ],
)

graph_n8n_workflows_percentages = Graph(
    name="n8n_workflows_percentages",
    title=Title("n8n Workflows - Percentages"),
    minimal_range=MinimalRange(0, 100),
    simple_lines=[
        "n8n_workflows_active_percent",
        "n8n_workflows_tagged_percent",
    ],
)

graph_n8n_workflows_averages = Graph(
    name="n8n_workflows_averages",
    title=Title("n8n Workflows - Averages"),
    simple_lines=[
        "n8n_workflows_avg_nodes",
        "n8n_workflows_avg_connections",
    ],
)

# --- Graphs: individual workflow ---------------------------------------------
graph_n8n_workflow_structure = Graph(
    name="n8n_workflow_structure",
    title=Title("Workflow Structure"),
    simple_lines=[
        "workflow_nodes",
        "workflow_connections",
        "workflow_complexity",
    ],
)

graph_n8n_workflow_executions_total = Graph(
    name="n8n_workflow_executions_total",
    title=Title("Workflow Executions (all time)"),
    compound_lines=[
        "workflow_successful_executions",
        "workflow_failed_executions",
    ],
    simple_lines=["workflow_total_executions"],
)

graph_n8n_workflow_executions_24h = Graph(
    name="n8n_workflow_executions_24h",
    title=Title("Workflow Executions (24h)"),
    compound_lines=[
        "workflow_successful_executions_24h",
        "workflow_failed_executions_24h",
    ],
    simple_lines=["workflow_total_executions_24h"],
)

graph_n8n_workflow_executions_8h = Graph(
    name="n8n_workflow_executions_8h",
    title=Title("Workflow Executions (8h)"),
    compound_lines=[
        "workflow_successful_executions_8h",
        "workflow_failed_executions_8h",
    ],
    simple_lines=["workflow_total_executions_8h"],
)

graph_n8n_workflow_success_rates = Graph(
    name="n8n_workflow_success_rates",
    title=Title("Workflow Success Rates"),
    minimal_range=MinimalRange(0, 100),
    simple_lines=[
        "workflow_success_rate",
        "workflow_success_rate_24h",
        "workflow_success_rate_8h",
    ],
)

graph_n8n_workflow_failure_duration = Graph(
    name="n8n_workflow_failure_duration",
    title=Title("Workflow Failure Duration"),
    simple_lines=[
        "workflow_avg_failure_duration",
        "workflow_failure_duration_p95",
        "workflow_failure_duration_p99",
    ],
)

# --- Perfometer --------------------------------------------------------------
# The success rate is the headline number for a workflow service.
perfometer_workflow_success_rate = Perfometer(
    name="workflow_success_rate",
    focus_range=FocusRange(Closed(0), Closed(100)),
    segments=["workflow_success_rate"],
)
