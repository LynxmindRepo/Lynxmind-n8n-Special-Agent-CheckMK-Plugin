#!/usr/bin/env python3
"""
n8n Variables Plugin for CheckMK
Monitors n8n variables data
"""

from typing import Dict, List, Optional
import sys
from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    StringTable,
    Metric,
)
from typing_extensions import TypedDict
import json


class N8nVariableInfo(TypedDict, total=False):
    variable_id: str
    variable_key: str
    variable_type: str
    created_at: str
    updated_at: str


class N8nVariablesInfo(TypedDict, total=False):
    total: int
    variables: List[N8nVariableInfo]


def parse_n8n_variables(string_table: StringTable) -> Optional[N8nVariablesInfo]:
    """Parse n8n_variables section"""
    if not string_table:
        return None

    try:
        variables_data = {
            'total': 0,
            'variables': []
        }

        for line in string_table:
            line_str = ' '.join(line)
            parts = line_str.split(';')

            if len(parts) >= 2:
                key = parts[0]
                value = parts[1]

                if key == 'total':
                    variables_data['total'] = int(value) if value.isdigit() else 0
                elif key == 'variable' and len(parts) >= 6:
                    variable_info = {
                        'variable_id': parts[1],
                        'variable_key': parts[2],
                        'variable_type': parts[3],
                        'created_at': parts[4],
                        'updated_at': parts[5]
                    }
                    variables_data['variables'].append(variable_info)

        return variables_data
    except (ValueError, IndexError):
        return None


def discover_n8n_variables(section: Optional[N8nVariablesInfo]) -> DiscoveryResult:
    """Discover n8n variables services"""
    if section is not None:
        # Create only one service for overall variable statistics
        yield Service()


def check_n8n_variables(section: Optional[N8nVariablesInfo]) -> CheckResult:
    """Check n8n variables overall statistics"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No variables data available")
        return

    total = section.get('total', 0)

    if total == 0:
        yield Result(state=State.WARN, summary="No variables found")
        return

    # Count variables by type
    variable_types = {}
    for variable in section.get('variables', []):
        var_type = variable.get('variable_type', 'unknown')
        variable_types[var_type] = variable_types.get(var_type, 0) + 1

    yield Result(
        state=State.OK,
        summary=f"Total variables: {total}"
    )

    # Add metrics
    yield Metric("n8n_variables_total", total)

    # Add variable type metrics
    for var_type, count in variable_types.items():
        yield Metric(f"n8n_variables_{var_type}", count)


# Individual variable check function removed for simplicity


# Register the agent section
agent_section_n8n_variables = AgentSection(
    name="n8n_variables",
    parse_function=parse_n8n_variables,
)

# Register check plugin for overall statistics
check_plugin_n8n_variables = CheckPlugin(
    name="n8n_variables",
    sections=["n8n_variables"],
    service_name="n8n Variables",
    discovery_function=discover_n8n_variables,
    check_function=check_n8n_variables,
)