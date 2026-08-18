
#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""
n8n Data Source for CheckMK
Defines data source for n8n monitoring
"""

from cmk.rulesets.v1.form_specs import (
    DictElement,
    Dictionary,
    BooleanChoice,
    Password,
    String,
    migrate_to_password,
    validators,
    Integer,
    DefaultValue,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic
from cmk.rulesets.v1 import Title, Help, Label


def _form_n8n_monitor() -> Dictionary:
    """Define the form elements for n8n special agent configuration"""
    return Dictionary(
        elements={
            "url": DictElement(
                parameter_form=String(
                    title=Title("n8n URL"),
                    help_text=Help("URL of the n8n instance (e.g., https://n8n.example.com)"),
                    custom_validate=(validators.LengthInRange(min_value=1),),
                ),
                required=True,
            ),
            "api_key": DictElement(
                parameter_form=Password(
                    title=Title("API Key"),
                    help_text=Help("n8n API key for authentication (JWT token)"),
                    migrate=migrate_to_password,
                ),
                required=False,
            ),
            "user": DictElement(
                parameter_form=String(
                    title=Title("Username"),
                    help_text=Help("n8n username for API authentication (optional)"),
                ),
                required=False,
            ),
            "api_password": DictElement(
                parameter_form=Password(
                    title=Title("User Password"),
                    help_text=Help("n8n password for API authentication (optional)"),
                    migrate=migrate_to_password,
                ),
                required=False,
            ),
            "timeout": DictElement(
                parameter_form=Integer(
                    title=Title("Timeout"),
                    help_text=Help("Timeout in seconds for HTTP requests"),
                    custom_validate=(validators.NumberInRange(min_value=1, max_value=300),),
                    prefill=DefaultValue(30),
                ),
                required=False,
            ),
            "healthz_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Health Check"),
                    help_text=Help(
                        "Probe the /healthz endpoint and create the 'n8n Health' service"
                    ),
                    label=Label("Enable Health Check"),
                    prefill=DefaultValue(True),
                ),
                required=False,
            ),
            "readiness_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Readiness Check"),
                    help_text=Help(
                        "Probe the /healthz/readiness endpoint and create the "
                        "'n8n Readiness' service"
                    ),
                    label=Label("Enable Readiness Check"),
                    prefill=DefaultValue(True),
                ),
                required=False,
            ),
            "metrics_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Metrics Collection"),
                    help_text=Help("Enable n8n metrics collection (/metrics endpoint)"),
                    label=Label("Enable Metrics Collection"),
                ),
                required=False,
            ),
            "executions_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Executions Collection"),
                    help_text=Help("Enable n8n executions collection (requires API key)"),
                    label=Label("Enable Executions Collection"),
                ),
                required=False,
            ),
            "workflows_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Workflows Collection"),
                    help_text=Help("Enable n8n workflows collection (requires API key)"),
                    label=Label("Enable Workflows Collection"),
                ),
                required=False,
            ),
            "workflow_executions_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Workflow Executions Analysis"),
                    help_text=Help(
                        "Enable the detailed per workflow execution analysis "
                        "(24h/8h success rates). Requires API key and "
                        "'Executions Collection'."
                    ),
                    label=Label("Enable Workflow Executions Analysis"),
                ),
                required=False,
            ),
            "failed_runs_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Failed Runs Analysis"),
                    help_text=Help(
                        "Enable the failed runs analysis with failure duration "
                        "percentiles (P95/P99) and the most recent failures per "
                        "workflow. Creates the 'n8n Failed Runs' service. "
                        "Requires API key."
                    ),
                    label=Label("Enable Failed Runs Analysis"),
                ),
                required=False,
            ),
            "users_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Users Collection"),
                    help_text=Help(
                        "Enable n8n users collection and create the 'n8n Users' "
                        "service (requires API key)"
                    ),
                    label=Label("Enable Users Collection"),
                ),
                required=False,
            ),
            "tags_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Tags Collection"),
                    help_text=Help(
                        "Enable n8n tags collection and create the 'n8n Tags' "
                        "service (requires API key)"
                    ),
                    label=Label("Enable Tags Collection"),
                ),
                required=False,
            ),
            "variables_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Variables Collection"),
                    help_text=Help("Enable n8n variables collection (requires API key)"),
                    label=Label("Enable Variables Collection"),
                ),
                required=False,
            ),
            "projects_enabled": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Projects Collection"),
                    help_text=Help("Enable n8n projects collection (requires API key)"),
                    label=Label("Enable Projects Collection"),
                ),
                required=False,
            ),
            "no_ssl_verify": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Disable SSL Verification"),
                    help_text=Help("Disable SSL certificate verification (not recommended for production)"),
                    label=Label("Disable SSL Verification"),
                ),
                required=False,
            ),
            "debug": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Debug Mode"),
                    help_text=Help("Enable debug logging for troubleshooting"),
                    label=Label("Enable Debug Logging"),
                ),
                required=False,
            ),
        },
        title=Title("n8n Monitor via API"),
    )


rule_spec_n8n_monitor = SpecialAgent(
    name="agent_n8n_monitor",
    title=Title("n8n Monitor via API"),
    topic=Topic.APPLICATIONS,
    parameter_form=_form_n8n_monitor,
)

