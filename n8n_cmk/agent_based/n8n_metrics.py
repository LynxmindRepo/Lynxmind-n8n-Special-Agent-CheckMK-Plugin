#!/usr/bin/env python3
"""
n8n Metrics Plugin for CheckMK
Parses n8n metrics data - individual services are handled by separate agent based plugins
"""

from typing import Dict, Optional
from cmk.agent_based.v2 import (
    AgentSection,
    StringTable,
)
from typing_extensions import TypedDict


class N8nMetricsInfo(TypedDict, total=False):
    endpoint: str
    url: str
    status_code: Optional[int]
    available: bool
    metrics: Dict
    error: Optional[str]
    timestamp: str


def parse_n8n_metrics(string_table: StringTable) -> Optional[N8nMetricsInfo]:
    """Parse n8n_metrics section"""
    if not string_table:
        return None

    try:
        # Parse the CheckMK format with key;value pairs
        # Filter out bucket metrics at parsing level to prevent automatic graph creation
        metrics_data = {}
        for line in string_table:
            line_str = ' '.join(line)
            if ';' in line_str:
                key, value = line_str.split(';', 1)
                key = key.strip()
                
                # Skip bucket metrics completely - they cause unwanted automatic graphs
                if 'bucket' in key.lower():
                    continue
                
                # For GC duration metrics, only keep sum metrics (not bucket or count)
                if 'gc_duration' in key.lower():
                    if 'sum' not in key.lower():
                        continue
                
                try:
                    # Try to convert to float, fallback to string
                    metrics_data[key] = float(value.strip())
                except ValueError:
                    metrics_data[key] = value.strip()

        return {
            'endpoint': 'metrics',
            'url': 'metrics',
            'available': True,
            'metrics': metrics_data,
            'timestamp': 'unknown'
        }
    except (ValueError, IndexError):
        return None


# Register the agent section
agent_section_n8n_metrics = AgentSection(
    name="n8n_metrics",
    parse_function=parse_n8n_metrics,
)
