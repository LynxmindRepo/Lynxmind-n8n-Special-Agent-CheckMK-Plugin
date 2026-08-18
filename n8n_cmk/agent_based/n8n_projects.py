#!/usr/bin/env python3
"""
n8n Projects Plugin for CheckMK
Monitors n8n projects data
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


class N8nProjectInfo(TypedDict, total=False):
    project_id: str
    project_name: str
    created_at: str
    updated_at: str


class N8nProjectsInfo(TypedDict, total=False):
    total: int
    projects: List[N8nProjectInfo]


def parse_n8n_projects(string_table: StringTable) -> Optional[N8nProjectsInfo]:
    """Parse n8n_projects section"""
    if not string_table:
        return None

    try:
        projects_data = {
            'total': 0,
            'projects': []
        }

        for line in string_table:
            line_str = ' '.join(line)
            parts = line_str.split(';')

            if len(parts) >= 2:
                key = parts[0]
                value = parts[1]

                if key == 'total':
                    projects_data['total'] = int(value) if value.isdigit() else 0
                elif key == 'project' and len(parts) >= 5:
                    project_info = {
                        'project_id': parts[1],
                        'project_name': parts[2],
                        'created_at': parts[3],
                        'updated_at': parts[4]
                    }
                    projects_data['projects'].append(project_info)

        return projects_data
    except (ValueError, IndexError):
        return None


def discover_n8n_projects(section: Optional[N8nProjectsInfo]) -> DiscoveryResult:
    """Discover n8n projects services"""
    if section is not None:
        # Create only one service for overall project statistics
        yield Service()


def check_n8n_projects(section: Optional[N8nProjectsInfo]) -> CheckResult:
    """Check n8n projects overall statistics"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No projects data available")
        return

    total = section.get('total', 0)

    if total == 0:
        yield Result(state=State.WARN, summary="No projects found")
        return

    yield Result(
        state=State.OK,
        summary=f"Total projects: {total}"
    )

    # Add metrics
    yield Metric("n8n_projects_total", total)


# Individual project check function removed for simplicity


# Register the agent section
agent_section_n8n_projects = AgentSection(
    name="n8n_projects",
    parse_function=parse_n8n_projects,
)

# Register check plugin for overall statistics
check_plugin_n8n_projects = CheckPlugin(
    name="n8n_projects",
    sections=["n8n_projects"],
    service_name="n8n Projects",
    discovery_function=discover_n8n_projects,
    check_function=check_n8n_projects,
)