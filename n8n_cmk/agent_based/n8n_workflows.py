#!/usr/bin/env python3
"""
n8n Workflows Plugin for CheckMK
Monitors n8n workflows data with detailed statistics
"""

from typing import Dict, List, Optional
import sys
from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    check_levels,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    ServiceLabel,
    State,
    StringTable,
    Metric,
)
from typing_extensions import TypedDict
import json


def _as_levels(levels):
    """Turn a normalized ``(warn, crit)`` pair into the ``check_levels`` shape."""
    return ("fixed", levels) if levels else ("no_levels", None)


class N8nWorkflowInfo(TypedDict, total=False):
    workflow_id: str
    workflow_name: str
    is_active: bool
    created_at: str
    updated_at: str
    tags: List[str]
    nodes_count: int
    connections_count: int


class N8nWorkflowsInfo(TypedDict, total=False):
    total: int
    active: int
    inactive: int
    workflows: List[N8nWorkflowInfo]
    recently_updated: int  # workflows updated in last 24h
    with_tags: int
    without_tags: int
    avg_nodes_per_workflow: float
    avg_connections_per_workflow: float
    most_complex_workflow: str
    least_complex_workflow: str


def parse_n8n_workflows(string_table: StringTable) -> Optional[N8nWorkflowsInfo]:
    """Parse n8n_workflows section"""
    if not string_table:
        return None

    try:
        workflows_data = {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'workflows': [],
            'recently_updated': 0,
            'with_tags': 0,
            'without_tags': 0,
            'avg_nodes_per_workflow': 0.0,
            'avg_connections_per_workflow': 0.0,
            'most_complex_workflow': '',
            'least_complex_workflow': ''
        }

        for line in string_table:
            line_str = ' '.join(line)
            parts = line_str.split(';')

            if len(parts) >= 2:
                key = parts[0]
                value = parts[1]

                if key == 'total':
                    workflows_data['total'] = int(value) if value.isdigit() else 0
                elif key == 'active':
                    workflows_data['active'] = int(value) if value.isdigit() else 0
                elif key == 'inactive':
                    workflows_data['inactive'] = int(value) if value.isdigit() else 0
                elif key == 'recently_updated':
                    workflows_data['recently_updated'] = int(value) if value.isdigit() else 0
                elif key == 'with_tags':
                    workflows_data['with_tags'] = int(value) if value.isdigit() else 0
                elif key == 'without_tags':
                    workflows_data['without_tags'] = int(value) if value.isdigit() else 0
                elif key == 'avg_nodes':
                    try:
                        workflows_data['avg_nodes_per_workflow'] = float(value)
                    except ValueError:
                        workflows_data['avg_nodes_per_workflow'] = 0.0
                elif key == 'avg_connections':
                    try:
                        workflows_data['avg_connections_per_workflow'] = float(value)
                    except ValueError:
                        workflows_data['avg_connections_per_workflow'] = 0.0
                elif key == 'most_complex':
                    workflows_data['most_complex_workflow'] = value
                elif key == 'least_complex':
                    workflows_data['least_complex_workflow'] = value
                elif key == 'workflow' and len(parts) >= 6:
                    # Parse individual workflow data with failed runs analysis
                    # Format: workflow;id;name;active;created;updated;tags;nodes;connections;total_executions;successful;failed;error;waiting;running;success_rate;total_24h;successful_24h;failed_24h;success_rate_24h;total_8h;successful_8h;failed_8h;success_rate_8h;avg_failure_duration;p95_failure_duration;p99_failure_duration;recent_failures
                    workflow_info = {
                        'workflow_id': parts[1],
                        'workflow_name': parts[2],
                        'is_active': parts[3].lower() == 'true',
                        'created_at': parts[4],
                        'updated_at': parts[5],
                        'tags': parts[6].split(',') if len(parts) > 6 and parts[6] else [],
                        'nodes_count': int(parts[7]) if len(parts) > 7 and parts[7].isdigit() else 0,
                        'connections_count': int(parts[8]) if len(parts) > 8 and parts[8].isdigit() else 0,
                        'total_executions': int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0,
                        'successful_executions': int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0,
                        'failed_executions': int(parts[11]) if len(parts) > 11 and parts[11].isdigit() else 0,
                        'error_executions': int(parts[12]) if len(parts) > 12 and parts[12].isdigit() else 0,
                        'waiting_executions': int(parts[13]) if len(parts) > 13 and parts[13].isdigit() else 0,
                        'running_executions': int(parts[14]) if len(parts) > 14 and parts[14].isdigit() else 0,
                        'success_rate': float(parts[15]) if len(parts) > 15 else 0.0,
                        # 24h statistics
                        'total_executions_24h': int(parts[16]) if len(parts) > 16 and parts[16].isdigit() else 0,
                        'successful_executions_24h': int(parts[17]) if len(parts) > 17 and parts[17].isdigit() else 0,
                        'failed_executions_24h': int(parts[18]) if len(parts) > 18 and parts[18].isdigit() else 0,
                        'success_rate_24h': float(parts[19]) if len(parts) > 19 else 0.0,
                        # 8h statistics
                        'total_executions_8h': int(parts[20]) if len(parts) > 20 and parts[20].isdigit() else 0,
                        'successful_executions_8h': int(parts[21]) if len(parts) > 21 and parts[21].isdigit() else 0,
                        'failed_executions_8h': int(parts[22]) if len(parts) > 22 and parts[22].isdigit() else 0,
                        'success_rate_8h': float(parts[23]) if len(parts) > 23 else 0.0,
                        # Failed runs analysis
                        'avg_failure_duration': float(parts[24]) if len(parts) > 24 else 0.0,
                        'failure_duration_p95': float(parts[25]) if len(parts) > 25 else 0.0,
                        'failure_duration_p99': float(parts[26]) if len(parts) > 26 else 0.0,
                        'recent_failures': []
                    }

                    # Parse recent failures if provided
                    if len(parts) > 27 and parts[27]:
                        try:
                            recent_failures_json = parts[27]
                            workflow_info['recent_failures'] = json.loads(recent_failures_json) if recent_failures_json != '[]' else []
                        except (json.JSONDecodeError, ValueError):
                            workflow_info['recent_failures'] = []

                    workflows_data['workflows'].append(workflow_info)

        return workflows_data
    except (ValueError, IndexError) as e:
        return None


def _normalize_levels(param_value, default=None):
    """Return a plain ``(warn, crit)`` tuple for any threshold parameter shape.

    The rulesets are built with ``SimpleLevels``, which stores the value as a
    two element tuple ``("fixed", (warn, crit))`` -- or ``("no_levels", None)``
    when the user switched the levels off.  Unpacking that tuple directly binds
    the warn variable to the string ``"fixed"`` and the crit variable to the
    inner tuple, so the next comparison raises
    ``TypeError: '<' not supported between instances of 'float' and 'tuple'``.

    Accepted shapes:

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


def discover_n8n_workflows(section: Optional[N8nWorkflowsInfo]) -> DiscoveryResult:
    """Discover n8n workflows services - only for overall statistics"""
    if section is not None:
        # Create only one service for overall workflow statistics
        yield Service()


def discover_n8n_workflow_items(section: Optional[N8nWorkflowsInfo]) -> DiscoveryResult:
    """Discover individual n8n workflow services with workflow name as label"""
    if section is not None:
        # Create individual services for each workflow
        for workflow in section.get('workflows', []):
            workflow_id = workflow.get('workflow_id')
            workflow_name = workflow.get('workflow_name', 'unknown')
            if workflow_id and workflow_id != 'unknown':
                # Create service labels
                service_labels = []

                # Add workflow name as a label in format n8n/tag:<nome_do_workflow>
                if workflow_name and workflow_name != 'unknown':
                    service_labels.append(
                        ServiceLabel("n8n/tag", workflow_name)
                    )

                # Use workflow name as item for better readability
                yield Service(item=workflow_name, labels=service_labels)


def check_n8n_workflows(
    params: Dict,
    section: Optional[N8nWorkflowsInfo],
) -> CheckResult:
    """Check n8n workflows overall statistics"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No workflows data available")
        return

    total = section.get('total', 0)
    active = section.get('active', 0)
    inactive = section.get('inactive', 0)
    recently_updated = section.get('recently_updated', 0)
    with_tags = section.get('with_tags', 0)
    without_tags = section.get('without_tags', 0)
    avg_nodes = section.get('avg_nodes_per_workflow', 0.0)
    avg_connections = section.get('avg_connections_per_workflow', 0.0)
    most_complex = section.get('most_complex_workflow', 'N/A')
    least_complex = section.get('least_complex_workflow', 'N/A')

    if total == 0:
        yield Result(state=State.WARN, summary="No workflows found")
        return

    # Calculate percentages
    active_percent = (active / total) * 100 if total > 0 else 0
    tagged_percent = (with_tags / total) * 100 if total > 0 else 0
    recent_update_percent = (recently_updated / total) * 100 if total > 0 else 0

    # Get thresholds from params (SimpleLevels, dict or plain tuple)
    total_workflows_levels = _normalize_levels(params.get('total_workflows'))
    inactive_workflows_levels = _normalize_levels(params.get('inactive_workflows'))

    # Main summary with key metrics.  The state comes from the configured
    # levels below; the share of inactive workflows is a deployment choice, not
    # a fault, so it no longer turns the service WARN/CRIT on its own.
    yield Result(
        state=State.OK,
        summary=f"Total: {total} workflows ({active} active, {inactive} inactive) - {active_percent:.1f}% active"
    )

    yield from check_levels(
        total,
        levels_upper=_as_levels(total_workflows_levels),
        metric_name="n8n_workflows_total",
        label="Workflows",
        render_func=lambda v: f"{v:.0f}",
        notice_only=True,
    )
    yield from check_levels(
        inactive,
        levels_upper=_as_levels(inactive_workflows_levels),
        metric_name="n8n_workflows_inactive",
        label="Inactive workflows",
        render_func=lambda v: f"{v:.0f}",
        notice_only=True,
    )

    # Additional details about workflow health
    details = []

    # Activity information
    if recently_updated > 0:
        details.append(f"{recently_updated} workflows updated recently ({recent_update_percent:.1f}%)")

    # Tag usage
    if with_tags > 0:
        details.append(f"{with_tags} with tags ({tagged_percent:.1f}%), {without_tags} without tags")

    # Complexity information
    if avg_nodes > 0:
        details.append(f"Avg complexity: {avg_nodes:.1f} nodes, {avg_connections:.1f} connections")

    if most_complex != 'N/A':
        details.append(f"Most complex: {most_complex}")

    # Output additional details
    for detail in details:
        yield Result(state=State.OK, summary=detail)

    # Workflow organization warning
    if total > 10 and tagged_percent < 30:
        yield Result(
            state=State.OK,
            summary=f"Only {tagged_percent:.1f}% of workflows are tagged - consider improving organization"
        )

    # Inactive workflows warning
    if inactive > active and total >= 5:
        yield Result(
            state=State.OK,
            summary=f"More inactive ({inactive}) than active ({active}) workflows - cleanup recommended"
        )

    # Complexity warnings
    if avg_nodes > 20:
        yield Result(
            state=State.OK,
            summary=f"Average workflow complexity is high ({avg_nodes:.1f} nodes) - consider simplification"
        )

    # Add comprehensive metrics
    yield Metric("n8n_workflows_active", active)
    yield Metric("n8n_workflows_active_percent", active_percent)
    yield Metric("n8n_workflows_recently_updated", recently_updated)
    yield Metric("n8n_workflows_with_tags", with_tags)
    yield Metric("n8n_workflows_without_tags", without_tags)
    yield Metric("n8n_workflows_tagged_percent", tagged_percent)
    yield Metric("n8n_workflows_avg_nodes", avg_nodes)
    yield Metric("n8n_workflows_avg_connections", avg_connections)


# Register the agent section
agent_section_n8n_workflows = AgentSection(
    name="n8n_workflows",
    parse_function=parse_n8n_workflows,
)

# Register check plugin for overall statistics
check_plugin_n8n_workflows = CheckPlugin(
    name="n8n_workflows",
    sections=["n8n_workflows"],
    service_name="n8n Workflows",
    discovery_function=discover_n8n_workflows,
    check_function=check_n8n_workflows,
    check_ruleset_name="n8n_workflows",
    check_default_parameters={},
)


def check_n8n_workflow_item(
    item: str,
    params: Dict,
    section: Optional[N8nWorkflowsInfo],
) -> CheckResult:
    """Check individual n8n workflow"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No workflows data available")
        return

    # Find the specific workflow by name
    workflow = None
    for wf in section.get('workflows', []):
        if wf.get('workflow_name') == item:
            workflow = wf
            break

    if workflow is None:
        yield Result(state=State.UNKNOWN, summary=f"Workflow '{item}' not found")
        return

    workflow_id = workflow.get('workflow_id', 'unknown')
    is_active = workflow.get('is_active', False)
    created_at = workflow.get('created_at', 'unknown')
    updated_at = workflow.get('updated_at', 'unknown')
    tags = workflow.get('tags', [])
    nodes_count = workflow.get('nodes_count', 0)
    connections_count = workflow.get('connections_count', 0)

    # Execution statistics
    total_executions = workflow.get('total_executions', 0)
    successful_executions = workflow.get('successful_executions', 0)
    failed_executions = workflow.get('failed_executions', 0)
    error_executions = workflow.get('error_executions', 0)
    waiting_executions = workflow.get('waiting_executions', 0)
    running_executions = workflow.get('running_executions', 0)
    success_rate = workflow.get('success_rate', 0)

    # Get 24h and 8h statistics (needed before the thresholds are evaluated)
    total_executions_24h = workflow.get('total_executions_24h', 0)
    successful_executions_24h = workflow.get('successful_executions_24h', 0)
    failed_executions_24h = workflow.get('failed_executions_24h', 0)
    success_rate_24h = workflow.get('success_rate_24h', 0)

    total_executions_8h = workflow.get('total_executions_8h', 0)
    successful_executions_8h = workflow.get('successful_executions_8h', 0)
    failed_executions_8h = workflow.get('failed_executions_8h', 0)
    success_rate_8h = workflow.get('success_rate_8h', 0)

    # Get thresholds from params (SimpleLevels, dict or plain tuple)
    success_rate_levels = _normalize_levels(
        params.get('success_rate'), (90.0, 70.0)
    )
    failed_executions_levels = _normalize_levels(params.get('failed_executions'))
    total_executions_24h_levels = _normalize_levels(params.get('total_executions_24h'))
    failed_executions_24h_levels = _normalize_levels(params.get('failed_executions_24h'))

    total_failed = failed_executions + error_executions

    # The status line only states what the workflow is.  Every WARN/CRIT is
    # produced by check_levels further down, so the ruleset genuinely governs
    # the service state and the levels also land in the perfdata.
    yield Result(state=State.OK, summary="Active" if is_active else "Inactive")

    # Get failed runs analysis
    avg_failure_duration = workflow.get('avg_failure_duration', 0)
    failure_duration_p95 = workflow.get('failure_duration_p95', 0)
    failure_duration_p99 = workflow.get('failure_duration_p99', 0)
    recent_failures = workflow.get('recent_failures', [])

    # Execution statistics with time-based analysis
    if total_executions > 0:
        yield Result(
            state=State.OK,
            summary=f"Executions: {total_executions} total, {successful_executions} successful, {failed_executions + error_executions} failed ({success_rate}% success rate)"
        )

        # Time-based execution breakdown
        if total_executions_24h > 0:
            yield Result(
                state=State.OK,
                summary=f"24h: {total_executions_24h} total, {successful_executions_24h} successful, {failed_executions_24h} failed ({success_rate_24h}% success rate)"
            )

        if total_executions_8h > 0:
            yield Result(
                state=State.OK,
                summary=f"8h: {total_executions_8h} total, {successful_executions_8h} successful, {failed_executions_8h} failed ({success_rate_8h}% success rate)"
            )

        # Failed runs analysis.  Informational only - the state for these
        # numbers comes from the failed_executions levels below.
        if total_failed > 0:

            if avg_failure_duration > 0:
                yield Result(
                    state=State.OK,
                    summary=f"Avg failure duration: {avg_failure_duration:.1f}s"
                )

            if failure_duration_p95 > 0:
                yield Result(
                    state=State.OK,
                    summary=f"Failure duration P95: {failure_duration_p95:.1f}s, P99: {failure_duration_p99:.1f}s"
                )

            # Recent failures details
            if recent_failures:
                yield Result(
                    state=State.OK,
                    summary=f"Recent failures: {len(recent_failures)}"
                )
                for failure in recent_failures[:3]:  # Show first 3 recent failures
                    error_message = failure.get('error_message', 'Unknown error')
                    error_node = failure.get('error_node', 'unknown')
                    started_at = failure.get('started_at', 'unknown')
                    duration = failure.get('duration', 0)

                    # Truncate long error messages
                    if len(error_message) > 50:
                        error_message = error_message[:47] + "..."

                    yield Result(
                        state=State.OK,
                        notice=f"✗ {error_node}: {error_message} ({duration:.1f}s) at {started_at}"
                    )

        # Detailed execution breakdown
        if successful_executions > 0:
            yield Result(
                state=State.OK,
                notice=f"✓ Successful: {successful_executions}"
            )
        if failed_executions > 0:
            yield Result(
                state=State.OK,
                notice=f"✗ Failed: {failed_executions}"
            )
        if error_executions > 0:
            yield Result(
                state=State.OK,
                notice=f"⚠ Errors: {error_executions}"
            )
        if waiting_executions > 0:
            yield Result(
                state=State.OK,
                notice=f"⏳ Waiting: {waiting_executions}"
            )
        if running_executions > 0:
            yield Result(
                state=State.OK,
                notice=f"🔄 Running: {running_executions}"
            )
    else:
        yield Result(
            state=State.OK,
            summary="No executions recorded"
        )

    # Complexity information
    complexity = nodes_count + connections_count
    if complexity > 0:
        yield Result(
            state=State.OK,
            summary=f"Complexity: {nodes_count} nodes, {connections_count} connections (total: {complexity})"
        )

        # Warning for very complex workflows
        if nodes_count > 50:
            yield Result(
                state=State.OK,
                summary=f"High complexity: {nodes_count} nodes may impact performance"
            )

    # Organization information
    if tags:
        tags_str = ', '.join(tags)
        yield Result(state=State.OK, summary=f"Tags: {tags_str}")
    else:
        yield Result(state=State.OK, summary="No tags - consider adding tags for better organization")

    # Timestamps
    yield Result(state=State.OK, summary=f"Created: {created_at}")
    yield Result(state=State.OK, summary=f"Last updated: {updated_at}")

    # Level checked values.  These both set the service state and put the
    # configured warn/crit into the perfdata, so the graphs show the
    # thresholds.  Only active workflows are judged: an inactive workflow keeps
    # its historical numbers but cannot be failing right now.
    if is_active:
        if total_executions > 0:
            yield from check_levels(
                success_rate,
                levels_lower=_as_levels(success_rate_levels),
                metric_name="workflow_success_rate",
                label="Success rate",
                render_func=lambda v: f"{v:.1f}%",
                notice_only=True,
            )
        else:
            # Nothing ran, so there is no rate to judge.
            yield Metric("workflow_success_rate", success_rate)

        yield from check_levels(
            total_failed,
            levels_upper=_as_levels(failed_executions_levels),
            metric_name="workflow_failed_executions",
            label="Failed runs",
            render_func=lambda v: f"{v:.0f}",
            notice_only=True,
        )
        yield from check_levels(
            failed_executions_24h,
            levels_upper=_as_levels(failed_executions_24h_levels),
            metric_name="workflow_failed_executions_24h",
            label="Failed runs (24h)",
            render_func=lambda v: f"{v:.0f}",
            notice_only=True,
        )
        yield from check_levels(
            total_executions_24h,
            levels_upper=_as_levels(total_executions_24h_levels),
            metric_name="workflow_total_executions_24h",
            label="Executions (24h)",
            render_func=lambda v: f"{v:.0f}",
            notice_only=True,
        )
    else:
        yield Metric("workflow_success_rate", success_rate)
        yield Metric("workflow_failed_executions", total_failed)
        yield Metric("workflow_failed_executions_24h", failed_executions_24h)
        yield Metric("workflow_total_executions_24h", total_executions_24h)

    # Metrics for graphing
    yield Metric("workflow_nodes", nodes_count)
    yield Metric("workflow_connections", connections_count)
    yield Metric("workflow_complexity", complexity)
    yield Metric("workflow_total_executions", total_executions)
    yield Metric("workflow_successful_executions", successful_executions)
    yield Metric("workflow_active", 1 if is_active else 0)

    # Time-based metrics
    yield Metric("workflow_successful_executions_24h", successful_executions_24h)
    yield Metric("workflow_success_rate_24h", success_rate_24h)
    yield Metric("workflow_total_executions_8h", total_executions_8h)
    yield Metric("workflow_successful_executions_8h", successful_executions_8h)
    yield Metric("workflow_failed_executions_8h", failed_executions_8h)
    yield Metric("workflow_success_rate_8h", success_rate_8h)

    # Failed runs analysis metrics
    yield Metric("workflow_avg_failure_duration", avg_failure_duration)
    yield Metric("workflow_failure_duration_p95", failure_duration_p95)
    yield Metric("workflow_failure_duration_p99", failure_duration_p99)
    yield Metric("workflow_recent_failures_count", len(recent_failures))


# Register check plugin for individual workflows
check_plugin_n8n_workflow_item = CheckPlugin(
    name="n8n_workflow_item",
    sections=["n8n_workflows"],
    service_name="n8n Workflow %s",
    discovery_function=discover_n8n_workflow_items,
    check_function=check_n8n_workflow_item,
    check_ruleset_name="n8n_workflow_item",
    check_default_parameters={},
)

