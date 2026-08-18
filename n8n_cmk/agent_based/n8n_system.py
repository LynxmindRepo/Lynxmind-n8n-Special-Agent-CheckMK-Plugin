#!/usr/bin/env python3
"""
n8n System Info Plugin for CheckMK
Monitors n8n system information
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
)
from typing_extensions import TypedDict
import json


class N8nSystemInfo(TypedDict, total=False):
    platform: str
    python_version: str
    timestamp: str
    agent_version: str


def parse_n8n_system(string_table: StringTable) -> Optional[N8nSystemInfo]:
    """Parse n8n_system section"""
    if not string_table:
        return None

    try:
        # Parse the CheckMK format: PLATFORM;AGENT_VERSION;TIMESTAMP
        line = ' '.join(string_table[0])
        parts = line.split(';')

        if len(parts) >= 3:
            platform = parts[0]
            agent_version = parts[1]
            timestamp = parts[2]

            return {
                'platform': platform,
                'agent_version': agent_version,
                'timestamp': timestamp
            }
    except (ValueError, IndexError):
        return None


def discover_n8n_system(section: Optional[N8nSystemInfo]) -> DiscoveryResult:
    """Discover n8n system service"""
    if section is not None:
        yield Service()


def check_n8n_system(section: Optional[N8nSystemInfo]) -> CheckResult:
    """Check n8n system information"""
    if section is None:
        yield Result(state=State.UNKNOWN, summary="No system data available")
        return

    platform_info = section.get('platform', 'Unknown')
    agent_version = section.get('agent_version', 'Unknown')
    timestamp = section.get('timestamp', 'Unknown')

    yield Result(
        state=State.OK,
        summary=f"Platform: {platform_info}, Agent: {agent_version}"
    )

    yield Result(
        state=State.OK,
        summary=f"Last update: {timestamp}"
    )


# Register the agent section
agent_section_n8n_system = AgentSection(
    name="n8n_system",
    parse_function=parse_n8n_system,
)

# Register check plugin
check_plugin_n8n_system = CheckPlugin(
    name="n8n_system",
    sections=["n8n_system"],
    service_name="n8n System Info",
    discovery_function=discover_n8n_system,
    check_function=check_n8n_system,
)
