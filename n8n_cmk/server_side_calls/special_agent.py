#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# (c) Elicarlos Ferreira <elicarlos.dias@lynxmind.com>
# License: GNU General Public License v2

from collections.abc import Iterator
from typing import Optional, List
from pydantic import BaseModel, Field

from cmk.server_side_calls.v1 import (
    HostConfig,
    Secret,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class Params(BaseModel):
    """params validator for n8n Monitor"""
    url: str = Field(..., description="n8n instance URL")
    api_key: Optional[Secret] = Field(None, description="n8n API key for authentication (JWT token)")
    user: Optional[str] = Field(None, description="n8n username for API authentication")
    api_password: Optional[Secret] = Field(None, description="n8n password for API authentication")
    timeout: int = Field(30, description="Request timeout in seconds")
    healthz_enabled: bool = Field(True, description="Enable health check monitoring")
    readiness_enabled: bool = Field(True, description="Enable readiness check monitoring")
    metrics_enabled: bool = Field(True, description="Enable metrics collection")
    executions_enabled: bool = Field(False, description="Enable executions collection")
    workflows_enabled: bool = Field(False, description="Enable workflows collection")
    users_enabled: bool = Field(False, description="Enable users collection")
    tags_enabled: bool = Field(False, description="Enable tags collection")
    variables_enabled: bool = Field(False, description="Enable variables collection")
    projects_enabled: bool = Field(False, description="Enable projects collection")
    failed_runs_enabled: bool = Field(False, description="Enable failed runs analysis with percentiles")
    workflow_executions_enabled: bool = Field(False, description="Enable detailed workflow executions analysis")
    no_ssl_verify: bool = Field(False, description="Disable SSL certificate verification")
    debug: bool = Field(False, description="Enable debug logging")


def _agent_n8n_arguments(
    params: Params, host_config: HostConfig
) -> Iterator[SpecialAgentCommand]:
    command_arguments: list[str | Secret] = [
        "--url", params.url,
    ]

    # The agent has no password store support, so the secrets have to be
    # handed over as plain text.
    if params.api_key:
        command_arguments += ["--api-key", params.api_key.unsafe()]

    if params.user:
        command_arguments += ["--user", params.user]

    if params.api_password:
        command_arguments += ["--api-password", params.api_password.unsafe()]

    command_arguments += [
        "--timeout", str(params.timeout),
        "--healthz-enabled", "true" if params.healthz_enabled else "false",
        "--readiness-enabled", "true" if params.readiness_enabled else "false",
        "--metrics-enabled", "true" if params.metrics_enabled else "false",
        "--executions-enabled", "true" if params.executions_enabled else "false",
        "--workflows-enabled", "true" if params.workflows_enabled else "false",
        "--users-enabled", "true" if params.users_enabled else "false",
        "--tags-enabled", "true" if params.tags_enabled else "false",
        "--variables-enabled", "true" if params.variables_enabled else "false",
        "--projects-enabled", "true" if params.projects_enabled else "false",
        "--failed-runs-enabled", "true" if params.failed_runs_enabled else "false",
        "--workflow-executions-enabled", "true" if params.workflow_executions_enabled else "false",
    ]

    if params.no_ssl_verify:
        command_arguments.append("--no-ssl-verify")
    
    if params.debug:
        command_arguments.append("--debug")

    yield SpecialAgentCommand(command_arguments=command_arguments)


special_agent_n8n_monitor = SpecialAgentConfig(
    name="n8n_monitor",
    parameter_parser=Params.model_validate,
    commands_function=_agent_n8n_arguments,
)
