6.#!/usr/bin/env python3
"""
n8n Monitoring Agent for CheckMK
Monitors n8n instance health and metrics endpoints
"""

import argparse
import asyncio
import aiohttp
import sys
import logging
import os
import platform
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import time
from collections.abc import MutableMapping, MutableSequence
from json import dumps as json_dumps
from time import time_ns

import tracemalloc 
tracemalloc.start()

# Default n8n endpoints
N8N_HEALTHZ_ENDPOINT = "/healthz"
N8N_READINESS_ENDPOINT = "/healthz/readiness"
N8N_METRICS_ENDPOINT = "/metrics"

# Timeout configuration
TIMEOUT = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)

# Path do timestamp compatível com Windows/Linux
# Tenta usar diretório do CheckMK primeiro, depois fallback para TEMP/tmp
def _get_checkmk_var_dir() -> Path:
    """Tenta encontrar o diretório var do CheckMK, senão usa TEMP/tmp"""
    # Tenta variável de ambiente do CheckMK
    omd_root = os.getenv("OMD_ROOT")
    if omd_root:
        var_dir = Path(omd_root) / "var" / "check_mk"
        var_dir.mkdir(parents=True, exist_ok=True)
        return var_dir
    
    # Tenta caminho padrão do CheckMK
    checkmk_var = Path("/omd/sites") / os.getenv("OMD_SITE", "default") / "var" / "check_mk"
    if checkmk_var.exists():
        checkmk_var.mkdir(parents=True, exist_ok=True)
        return checkmk_var
    
    # Fallback para TEMP/tmp
    return Path(os.getenv("TEMP", "/tmp"))

TIMESTAMP_FILE = _get_checkmk_var_dir() / "n8n_last_run.txt"
# Path do timestamp de ativação do plugin
ACTIVATION_TIMESTAMP_FILE = _get_checkmk_var_dir() / "n8n_activation_timestamp.txt"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_activation_timestamp() -> Optional[datetime]:
    """
    Obtém o timestamp de ativação do plugin.
    Se não existir, cria um novo com o timestamp atual.
    """
    try:
        if ACTIVATION_TIMESTAMP_FILE.exists():
            with open(ACTIVATION_TIMESTAMP_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                if timestamp_str:
                    # Pode ser um timestamp Unix ou ISO
                    try:
                        # Tenta como timestamp Unix
                        timestamp_float = float(timestamp_str)
                        return datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
                    except ValueError:
                        # Tenta como ISO format
                        try:
                            if timestamp_str.endswith('Z'):
                                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            return datetime.fromisoformat(timestamp_str)
                        except ValueError:
                            pass
    except Exception as e:
        logger.debug(f"Error reading activation timestamp: {e}")
    
    # Se não existe ou houve erro, cria um novo timestamp de ativação
    activation_time = datetime.now(timezone.utc)
    try:
        with open(ACTIVATION_TIMESTAMP_FILE, 'w') as f:
            f.write(activation_time.isoformat())
        logger.info(f"Created new activation timestamp: {activation_time.isoformat()}")
        logger.info(f"Activation timestamp file location: {ACTIVATION_TIMESTAMP_FILE}")
    except Exception as e:
        logger.warning(f"Could not save activation timestamp to {ACTIVATION_TIMESTAMP_FILE}: {e}")
    
    return activation_time

def filter_by_activation_time(executions_list: List[Dict], activation_time: Optional[datetime]) -> List[Dict]:
    """
    Filtra execuções para incluir apenas aquelas que ocorreram após o timestamp de ativação.
    """
    if not activation_time:
        return executions_list
    
    filtered = []
    for execution in executions_list:
        started_at_str = execution.get('startedAt')
        if not started_at_str:
            continue
        
        try:
            # Parse timestamp
            if started_at_str.endswith('Z'):
                started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
            else:
                started_at = datetime.fromisoformat(started_at_str)
            
            # Inclui apenas execuções após a ativação
            if started_at >= activation_time:
                filtered.append(execution)
        except (ValueError, TypeError):
            # Se não conseguir parsear, inclui por segurança (mas loga)
            logger.debug(f"Could not parse timestamp: {started_at_str}")
            continue
    
    return filtered

def parse_args():
    parser = argparse.ArgumentParser(description="n8n Monitoring Agent for CheckMK")
    # The single dash spellings are kept as aliases so rules written against
    # older releases keep working.
    parser.add_argument("--url", "-url", required=True, help="n8n instance URL (e.g., https://your-n8n-instance.com)")
    parser.add_argument("--user", "-user", help="n8n username for API authentication")
    parser.add_argument("--api-password", "-api-password", help="n8n password for API authentication")
    parser.add_argument("--api-key", "-api-key", help="n8n API key for authentication")
    parser.add_argument("--metrics-enabled", default="true", help="Enable metrics collection (true/false)")
    parser.add_argument("--healthz-enabled", default="true", help="Enable healthz collection (true/false)")
    parser.add_argument("--readiness-enabled", default="true", help="Enable readiness collection (true/false)")
    parser.add_argument("--executions-enabled", default="true", help="Enable executions collection (true/false)")
    parser.add_argument("--workflows-enabled", default="true", help="Enable workflows collection (true/false)")
    parser.add_argument("--users-enabled", default="true", help="Enable users collection (true/false)")
    parser.add_argument("--tags-enabled", default="true", help="Enable tags collection (true/false)")
    parser.add_argument("--variables-enabled", default="true", help="Enable variables collection (true/false)")
    parser.add_argument("--projects-enabled", default="true", help="Enable projects collection (true/false)")
    parser.add_argument("--failed-runs-enabled", default="true", help="Enable failed runs analysis collection (true/false)")
    parser.add_argument("--workflow-executions-enabled", default="true", help="Enable workflow executions analysis collection (true/false)")
    parser.add_argument("--no-ssl-verify", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

class N8nMonitor:
    def __init__(self, base_url: str, timeout: int = 30, verify_ssl: bool = True, username: str = None, password: str = None, api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=5, sock_read=10)
        self.verify_ssl = verify_ssl
        self.username = username
        self.password = password
        self.api_key = api_key
        self.session = None
        # workflow id -> name, filled in by get_workflows().  The executions
        # endpoint is queried with includeData=false and therefore carries no
        # workflowData.name, so without this map every derived section would
        # report the workflow as "unknown".
        self.workflow_names: Dict[str, str] = {}

    def _resolve_workflow_name(self, execution: Dict) -> str:
        """Best effort workflow name for one execution record."""
        name = (execution.get('workflowData') or {}).get('name')
        if name:
            return name
        workflow_id = execution.get('workflowId')
        if workflow_id is not None:
            return self.workflow_names.get(str(workflow_id)) or f"id:{workflow_id}"
        return "unknown"

    def _auth_headers(self) -> Dict:
        headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
        if self.api_key:
            headers['X-N8N-API-KEY'] = self.api_key
        elif self.username and self.password:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        return headers

    async def _fetch_all_executions(
        self, activation_time: Optional[datetime] = None, max_pages: int = 50
    ) -> List[Dict]:
        """Page through /api/v1/executions, newest first, until exhausted.

        n8n caps ``limit`` at 250 server-side no matter what is requested, so
        a single request only ever sees the newest ~250 executions. On a busy
        instance (thousands/day) every stat derived from a single page was
        silently truncated to the last couple of hours. Executions come back
        newest-first, so paging stops as soon as a page's oldest entry
        predates ``activation_time`` - no need to page all the way to
        n8n's own end of history.
        """
        headers = self._auth_headers()
        url = f"{self.base_url}/api/v1/executions"
        all_executions: List[Dict] = []
        cursor = None

        for page_num in range(max_pages):
            params = {'limit': 250, 'includeData': 'false'}
            if cursor:
                params['cursor'] = cursor

            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    raise RuntimeError(f"executions API returned HTTP {response.status}")
                if 'application/json' not in response.headers.get('content-type', ''):
                    raise RuntimeError("executions API returned a non-JSON response")
                payload = await response.json()

            page = payload.get('data', [])
            all_executions.extend(page)
            cursor = payload.get('nextCursor')

            if not cursor:
                break
            if activation_time and page:
                oldest_started_at = page[-1].get('startedAt', '')
                try:
                    ts = oldest_started_at.replace('Z', '+00:00')
                    if datetime.fromisoformat(ts) < activation_time:
                        break
                except (ValueError, AttributeError):
                    pass
        else:
            # ponytail: hard cap at 50 pages / 12500 executions so a
            # multi-year-old activation timestamp can't make this loop
            # forever. Fine for the "since we started watching" numbers this
            # agent reports, wrong for a true unbounded lifetime counter -
            # that needs an incrementally persisted counter, not a full
            # re-fetch every run. Raise max_pages if 4-5 days of executions
            # (at a few thousand/day) stops being enough headroom.
            logger.warning(
                f"Stopped paging executions at the {max_pages}-page safety cap "
                f"({len(all_executions)} executions); older history since "
                f"activation may be missing from this run's stats."
            )

        if activation_time:
            original_count = len(all_executions)
            all_executions = filter_by_activation_time(all_executions, activation_time)
            logger.info(
                f"Filtered executions: {original_count} -> {len(all_executions)} "
                f"(after activation: {activation_time.isoformat()})"
            )

        return all_executions

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={'User-Agent': 'n8n-monitor-agent/1.0'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def check_healthz(self) -> Dict:
        """Check n8n healthz endpoint"""
        try:
            url = f"{self.base_url}{N8N_HEALTHZ_ENDPOINT}"
            started = time.time()
            async with self.session.get(url) as response:
                status_code = response.status
                # elapsed seconds, not an absolute timestamp
                response_time = time.time() - started

                return {
                    "endpoint": "healthz",
                    "url": url,
                    "status_code": status_code,
                    "healthy": status_code == 200,
                    "response_time": response_time,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            return {
                "endpoint": "healthz",
                "url": url,
                "status_code": None,
                "healthy": False,
                "error": str(e),
                "response_time": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def check_readiness(self) -> Dict:
        """Check n8n readiness endpoint"""
        try:
            url = f"{self.base_url}{N8N_READINESS_ENDPOINT}"
            started = time.time()
            async with self.session.get(url) as response:
                status_code = response.status
                # elapsed seconds, not an absolute timestamp
                response_time = time.time() - started

                return {
                    "endpoint": "readiness",
                    "url": url,
                    "status_code": status_code,
                    "ready": status_code == 200,
                    "response_time": response_time,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            return {
                "endpoint": "readiness",
                "url": url,
                "status_code": None,
                "ready": False,
                "error": str(e),
                "response_time": None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def get_metrics(self) -> Dict:
        """Get n8n metrics endpoint"""
        try:
            url = f"{self.base_url}{N8N_METRICS_ENDPOINT}"
            async with self.session.get(url) as response:
                status_code = response.status
                response_time = time.time()
                
                if status_code == 200:
                    metrics_text = await response.text()
                    # Parse Prometheus metrics format
                    metrics = self._parse_prometheus_metrics(metrics_text)
                else:
                    metrics = {}
                
                return {
                    "endpoint": "metrics",
                    "url": url,
                    "status_code": status_code,
                    "available": status_code == 200,
                    "response_time": response_time,
                    "metrics": metrics,
                    "raw_metrics": metrics_text if status_code == 200 else None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            return {
                "endpoint": "metrics",
                "url": url,
                "status_code": None,
                "available": False,
                "error": str(e),
                "response_time": None,
                "metrics": {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def get_executions(self, activation_time: Optional[datetime] = None) -> Dict:
        """
        Get n8n executions data using API v1
        GET /api/v1/executions?limit=250&includeData=false
        Filtra apenas execuções após o timestamp de ativação.
        """
        try:
            executions_list = await self._fetch_all_executions(activation_time)
            logger.info(f"Successfully retrieved {len(executions_list)} executions")

            return {
                "endpoint": "executions",
                "url": f"{self.base_url}/api/v1/executions",
                "status_code": 200,
                "available": True,
                "executions": {"data": executions_list},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Exception accessing executions API: {e}")
        
        return {
            "endpoint": "executions",
            "url": f"{self.base_url}/api/v1/executions",
            "status_code": None,
            "available": False,
            "error": "Failed to retrieve executions",
            "executions": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_workflows(self, activation_time: Optional[datetime] = None, executions_cache: Optional[List[Dict]] = None) -> Dict:
        """
        Get n8n workflows data using API v1 with execution statistics
        GET /api/v1/workflows?limit=250&excludePinnedData=true
        Filtra apenas execuções após o timestamp de ativação.
        Otimizado para reutilizar dados de execuções já coletados.
        """
        try:
            # Use API v1 endpoint with proper parameters
            url = f"{self.base_url}/api/v1/workflows"
            params = {
                'limit': 250,  # Maximum allowed
                'excludePinnedData': 'true'  # Avoid large data transfers
            }
            
            logger.debug(f"Accessing workflows API: {url} with params: {params}")
            
            headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
            if self.api_key:
                headers['X-N8N-API-KEY'] = self.api_key
                logger.debug("Using API Key authentication for workflows")
            elif self.username and self.password:
                import base64
                credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
                logger.debug("Using Basic authentication for workflows")
            
            async with self.session.get(url, headers=headers, params=params) as response:
                logger.debug(f"Workflows API response status: {response.status}")
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        workflows_data = await response.json()
                        workflows_list = workflows_data.get('data', [])
                        logger.info(f"Successfully retrieved {len(workflows_list)} workflows")

                        # Remember the names so the executions based sections
                        # can label their rows.
                        self.workflow_names = {
                            str(w.get('id')): w.get('name', 'unknown')
                            for w in workflows_list
                            if w.get('id') is not None
                        }
                        
                        # Get execution statistics for all workflows at once (otimizado)
                        # Se temos cache de execuções, usa ele; senão, busca uma vez
                        if executions_cache is None:
                            executions_cache = await self._fetch_all_executions(activation_time)
                        
                        # Calcular estatísticas para cada workflow usando o cache
                        workflows_with_stats = []
                        for workflow in workflows_list:
                            workflow_id = workflow.get('id')
                            if workflow_id and executions_cache:
                                # Calcular stats usando dados já coletados (muito mais rápido)
                                execution_stats = self._calculate_workflow_stats_from_cache(
                                    workflow_id, executions_cache, activation_time
                                )
                                workflow['execution_stats'] = execution_stats
                            else:
                                # Fallback: stats vazias se não houver dados
                                workflow['execution_stats'] = {
                                    'total_executions': 0,
                                    'successful_executions': 0,
                                    'failed_executions': 0,
                                    'error_executions': 0,
                                    'waiting_executions': 0,
                                    'running_executions': 0,
                                    'success_rate': 100,
                                    'total_executions_24h': 0,
                                    'successful_executions_24h': 0,
                                    'failed_executions_24h': 0,
                                    'success_rate_24h': 100,
                                    'total_executions_8h': 0,
                                    'successful_executions_8h': 0,
                                    'failed_executions_8h': 0,
                                    'success_rate_8h': 100,
                                    'avg_failure_duration': 0,
                                    'failure_duration_p95': 0,
                                    'failure_duration_p99': 0,
                                    'recent_failures': []
                                }
                            workflows_with_stats.append(workflow)
                        
                        workflows_data['data'] = workflows_with_stats
                        
                        return {
                            "endpoint": "workflows",
                            "url": url,
                            "status_code": response.status,
                            "available": True,
                            "workflows": workflows_data,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        logger.error(f"Unexpected content-type: {content_type}")
                elif response.status == 401:
                    logger.error("Authentication failed for workflows API - check API key")
                else:
                    logger.error(f"Workflows API returned status {response.status}")
                    error_text = await response.text()
                    logger.debug(f"Error response: {error_text[:200]}")
                    
        except Exception as e:
            logger.error(f"Exception accessing workflows API: {e}")
        
        return {
            "endpoint": "workflows",
            "url": f"{self.base_url}/api/v1/workflows",
            "status_code": None,
            "available": False,
            "error": "Failed to retrieve workflows",
            "workflows": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _calculate_workflow_stats_from_cache(self, workflow_id: str, executions_list: List[Dict], activation_time: Optional[datetime] = None) -> Dict:
        """
        Calcula estatísticas de execução para um workflow usando dados já coletados.
        Muito mais rápido que fazer uma nova chamada de API.
        """
        # Filter executions for this specific workflow
        workflow_executions = [
            exec for exec in executions_list 
            if exec.get('workflowId') == workflow_id
        ]
        
        logger.debug(f"Calculating stats for workflow {workflow_id} from {len(workflow_executions)} executions")
        
        # Calculate basic statistics
        total_executions = len(workflow_executions)
        successful_executions = 0
        failed_executions = 0
        error_executions = 0
        waiting_executions = 0
        running_executions = 0
        
        # Analyze failed runs with time filtering and percentiles
        from datetime import datetime, timedelta, timezone
        import statistics
        
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_8h = now - timedelta(hours=8)
        
        executions_24h = []
        executions_8h = []
        failure_durations = []
        recent_failures = []
        
        for execution in workflow_executions:
            status = execution.get('status', 'unknown')
            
            # Basic status counting
            if status == 'success':
                successful_executions += 1
            elif status == 'error':
                error_executions += 1
            elif status == 'failed':
                failed_executions += 1
            elif status == 'waiting':
                waiting_executions += 1
            elif status == 'running':
                running_executions += 1
        
            # Time-based analysis
            started_at_str = execution.get('startedAt')
            if started_at_str:
                try:
                    if started_at_str.endswith('Z'):
                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                    else:
                        started_at = datetime.fromisoformat(started_at_str)
                    
                    # Categorize by time period
                    if started_at >= cutoff_24h:
                        executions_24h.append(execution)
                    if started_at >= cutoff_8h:
                        executions_8h.append(execution)
                    
                    # Analyze failed executions for percentiles
                    if status in ['error', 'failed']:
                        finished_at_str = execution.get('finishedAt')
                        if finished_at_str:
                            try:
                                if finished_at_str.endswith('Z'):
                                    finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                                else:
                                    finished_at = datetime.fromisoformat(finished_at_str)
                                duration = (finished_at - started_at).total_seconds()
                                failure_durations.append(duration)
                                
                                # Collect recent failures (last 5)
                                if len(recent_failures) < 5:
                                    error_data = execution.get('data', {}).get('resultData', {}).get('runData', {}).get('error', {})
                                    error_message = error_data.get('message', 'Unknown error') if error_data else 'Unknown error'
                                    error_node = error_data.get('node', {}).get('name', 'unknown') if error_data else 'unknown'
                                    
                                    recent_failures.append({
                                        'execution_id': execution.get('id', 'unknown'),
                                        'error_message': error_message,
                                        'error_node': error_node,
                                        'started_at': started_at_str,
                                        'duration': duration
                                    })
                            except (ValueError, TypeError):
                                pass
                except (ValueError, TypeError):
                    pass
        
        # Calculate 24h and 8h statistics
        total_24h = len(executions_24h)
        failed_24h = len([e for e in executions_24h if e.get('status') in ['error', 'failed']])
        successful_24h = len([e for e in executions_24h if e.get('status') == 'success'])
        success_rate_24h = (successful_24h / total_24h * 100) if total_24h > 0 else 100
        
        total_8h = len(executions_8h)
        failed_8h = len([e for e in executions_8h if e.get('status') in ['error', 'failed']])
        successful_8h = len([e for e in executions_8h if e.get('status') == 'success'])
        success_rate_8h = (successful_8h / total_8h * 100) if total_8h > 0 else 100
        
        # Calculate percentiles
        avg_failure_duration = statistics.mean(failure_durations) if failure_durations else 0
        p95_failure_duration = statistics.quantiles(failure_durations, n=20)[18] if len(failure_durations) >= 20 else (max(failure_durations) if failure_durations else 0)
        p99_failure_duration = statistics.quantiles(failure_durations, n=100)[98] if len(failure_durations) >= 100 else (max(failure_durations) if failure_durations else 0)
        
        # Calculate overall success rate
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 100
        
        logger.debug(f"Workflow {workflow_id} stats: {total_executions} total, {successful_executions} successful, {failed_executions + error_executions} failed")
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'failed_executions': failed_executions,
            'error_executions': error_executions,
            'waiting_executions': waiting_executions,
            'running_executions': running_executions,
            'success_rate': round(success_rate, 2),
            # 24h statistics
            'total_executions_24h': total_24h,
            'successful_executions_24h': successful_24h,
            'failed_executions_24h': failed_24h,
            'success_rate_24h': round(success_rate_24h, 2),
            # 8h statistics
            'total_executions_8h': total_8h,
            'successful_executions_8h': successful_8h,
            'failed_executions_8h': failed_8h,
            'success_rate_8h': round(success_rate_8h, 2),
            # Failed runs analysis
            'avg_failure_duration': round(avg_failure_duration, 2),
            'failure_duration_p95': round(p95_failure_duration, 2),
            'failure_duration_p99': round(p99_failure_duration, 2),
            'recent_failures': recent_failures
        }

    async def get_workflow_execution_stats(self, workflow_id: str, headers: Dict, activation_time: Optional[datetime] = None) -> Dict:
        """
        Get execution statistics for a specific workflow with failed runs analysis
        Filtra apenas execuções após o timestamp de ativação.
        """
        try:
            # Get executions with more data for failed runs analysis
            url = f"{self.base_url}/api/v1/executions"
            params = {
                'limit': 200,  # Get more executions for better analysis
                'includeData': 'false'  # Don't include execution data, just metadata
            }
            
            logger.debug(f"Getting execution stats for workflow {workflow_id}")
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        executions_data = await response.json()
                        executions_list = executions_data.get('data', [])
                        
                        # Filtrar por timestamp de ativação primeiro
                        if activation_time:
                            executions_list = filter_by_activation_time(executions_list, activation_time)
                        
                        # Filter executions for this specific workflow
                        workflow_executions = [
                            exec for exec in executions_list 
                            if exec.get('workflowId') == workflow_id
                        ]
                        
                        logger.debug(f"Found {len(workflow_executions)} executions for workflow {workflow_id}")
                        
                        # Calculate basic statistics
                        total_executions = len(workflow_executions)
                        successful_executions = 0
                        failed_executions = 0
                        error_executions = 0
                        waiting_executions = 0
                        running_executions = 0
                        
                        # Analyze failed runs with time filtering and percentiles
                        from datetime import datetime, timedelta, timezone
                        import statistics
                        
                        now = datetime.now(timezone.utc)
                        cutoff_24h = now - timedelta(hours=24)
                        cutoff_8h = now - timedelta(hours=8)
                        
                        executions_24h = []
                        executions_8h = []
                        failure_durations = []
                        recent_failures = []
                        
                        for execution in workflow_executions:
                            status = execution.get('status', 'unknown')
                            
                            # Basic status counting
                            if status == 'success':
                                successful_executions += 1
                            elif status == 'error':
                                error_executions += 1
                            elif status == 'failed':
                                failed_executions += 1
                            elif status == 'waiting':
                                waiting_executions += 1
                            elif status == 'running':
                                running_executions += 1
                        
                            # Time-based analysis
                            started_at_str = execution.get('startedAt')
                            if started_at_str:
                                try:
                                    if started_at_str.endswith('Z'):
                                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                                    else:
                                        started_at = datetime.fromisoformat(started_at_str)
                                    
                                    # Categorize by time period
                                    if started_at >= cutoff_24h:
                                        executions_24h.append(execution)
                                    if started_at >= cutoff_8h:
                                        executions_8h.append(execution)
                                    
                                    # Analyze failed executions for percentiles
                                    if status in ['error', 'failed']:
                                        finished_at_str = execution.get('finishedAt')
                                        if finished_at_str:
                                            try:
                                                if finished_at_str.endswith('Z'):
                                                    finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                                                else:
                                                    finished_at = datetime.fromisoformat(finished_at_str)
                                                duration = (finished_at - started_at).total_seconds()
                                                failure_durations.append(duration)
                                                
                                                # Collect recent failures (last 5)
                                                if len(recent_failures) < 5:
                                                    error_data = execution.get('data', {}).get('resultData', {}).get('runData', {}).get('error', {})
                                                    error_message = error_data.get('message', 'Unknown error') if error_data else 'Unknown error'
                                                    error_node = error_data.get('node', {}).get('name', 'unknown') if error_data else 'unknown'
                                                    
                                                    recent_failures.append({
                                                        'execution_id': execution.get('id', 'unknown'),
                                                        'error_message': error_message,
                                                        'error_node': error_node,
                                                        'started_at': started_at_str,
                                                        'duration': duration
                                                    })
                                            except (ValueError, TypeError):
                                                pass
                                except (ValueError, TypeError):
                                    pass
                        
                        # Calculate 24h and 8h statistics
                        total_24h = len(executions_24h)
                        failed_24h = len([e for e in executions_24h if e.get('status') in ['error', 'failed']])
                        successful_24h = len([e for e in executions_24h if e.get('status') == 'success'])
                        success_rate_24h = (successful_24h / total_24h * 100) if total_24h > 0 else 100
                        
                        total_8h = len(executions_8h)
                        failed_8h = len([e for e in executions_8h if e.get('status') in ['error', 'failed']])
                        successful_8h = len([e for e in executions_8h if e.get('status') == 'success'])
                        success_rate_8h = (successful_8h / total_8h * 100) if total_8h > 0 else 100
                        
                        # Calculate percentiles
                        avg_failure_duration = statistics.mean(failure_durations) if failure_durations else 0
                        p95_failure_duration = statistics.quantiles(failure_durations, n=20)[18] if len(failure_durations) >= 20 else (max(failure_durations) if failure_durations else 0)
                        p99_failure_duration = statistics.quantiles(failure_durations, n=100)[98] if len(failure_durations) >= 100 else (max(failure_durations) if failure_durations else 0)
                        
                        # Calculate overall success rate
                        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 100
                        
                        logger.debug(f"Workflow {workflow_id} stats: {total_executions} total, {successful_executions} successful, {failed_executions + error_executions} failed")
                        
                        return {
                            'total_executions': total_executions,
                            'successful_executions': successful_executions,
                            'failed_executions': failed_executions,
                            'error_executions': error_executions,
                            'waiting_executions': waiting_executions,
                            'running_executions': running_executions,
                            'success_rate': round(success_rate, 2),
                            # 24h statistics
                            'total_executions_24h': total_24h,
                            'successful_executions_24h': successful_24h,
                            'failed_executions_24h': failed_24h,
                            'success_rate_24h': round(success_rate_24h, 2),
                            # 8h statistics
                            'total_executions_8h': total_8h,
                            'successful_executions_8h': successful_8h,
                            'failed_executions_8h': failed_8h,
                            'success_rate_8h': round(success_rate_8h, 2),
                            # Failed runs analysis
                            'avg_failure_duration': round(avg_failure_duration, 2),
                            'failure_duration_p95': round(p95_failure_duration, 2),
                            'failure_duration_p99': round(p99_failure_duration, 2),
                            'recent_failures': recent_failures
                        }
                        
        except Exception as e:
            logger.debug(f"Could not get execution stats for workflow {workflow_id}: {e}")
        
        return {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'error_executions': 0,
            'waiting_executions': 0,
            'running_executions': 0,
            'success_rate': 100,
            'total_executions_24h': 0,
            'successful_executions_24h': 0,
            'failed_executions_24h': 0,
            'success_rate_24h': 100,
            'total_executions_8h': 0,
            'successful_executions_8h': 0,
            'failed_executions_8h': 0,
            'success_rate_8h': 100,
            'avg_failure_duration': 0,
            'failure_duration_p95': 0,
            'failure_duration_p99': 0,
            'recent_failures': []
        }

    async def get_workflow_executions_analysis(self, activation_time: Optional[datetime] = None, executions_cache: Optional[List[Dict]] = None) -> Dict:
        """
        Get detailed workflow executions analysis with time-based filtering and percentiles
        Filtra apenas execuções após o timestamp de ativação.
        Otimizado para reutilizar dados de execuções já coletados.
        """
        try:
            executions_list = executions_cache
            
            # Se não temos cache, buscar execuções
            if executions_list is None:
                logger.debug("Getting workflow executions analysis data")
                try:
                    executions_list = await self._fetch_all_executions(activation_time)
                except Exception as e:
                    logger.error(f"Failed to fetch executions for workflow analysis: {e}")
                    executions_list = None
            else:
                logger.info(f"Reusing cached executions for workflow analysis: {len(executions_list)} executions")

            # ``None`` means the fetch failed; an empty list is a valid answer
            # (the instance genuinely has no executions) and must be analyzed
            # so the zeros we report are real rather than invented.
            if executions_list is not None:
                logger.info(f"Analyzing {len(executions_list)} executions for workflow analysis")
                
                # Analyze executions by workflow and time periods
                analysis = self._analyze_workflow_executions(executions_list)
                
                return {
                    "endpoint": "workflow_executions_analysis",
                    "url": f"{self.base_url}/api/v1/executions",
                    "status_code": 200,
                    "available": True,
                    "analysis": analysis,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                        
        except Exception as e:
            logger.error(f"Exception in workflow executions analysis: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Reached only when the executions could not be retrieved.  Reporting
        # zeros here would make an unreachable n8n look like "no failures", so
        # the section is suppressed and the service goes stale instead.
        return {
            "endpoint": "workflow_executions_analysis",
            "url": f"{self.base_url}/api/v1/executions",
            "status_code": None,
            "available": False,
            "error": "executions data unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_failed_runs_analysis(self, activation_time: Optional[datetime] = None, executions_cache: Optional[List[Dict]] = None) -> Dict:
        """
        Get detailed failed runs analysis with time-based filtering and percentiles
        Filtra apenas execuções após o timestamp de ativação.
        Otimizado para reutilizar dados de execuções já coletados.
        """
        try:
            executions_list = executions_cache
            
            # Se não temos cache, buscar execuções
            if executions_list is None:
                logger.debug("Getting failed runs analysis data")
                try:
                    executions_list = await self._fetch_all_executions(activation_time)
                except Exception as e:
                    logger.error(f"Failed to fetch executions for failed runs analysis: {e}")
                    executions_list = None
            else:
                logger.info(f"Reusing cached executions for failed runs analysis: {len(executions_list)} executions")

            # See get_workflow_executions_analysis: ``None`` is a failed fetch,
            # ``[]`` is a real "nothing ran yet".
            if executions_list is not None:
                logger.info(f"Analyzing {len(executions_list)} executions for failed runs")
                
                # Analyze executions by workflow and time periods
                analysis = self._analyze_failed_runs(executions_list)
                
                return {
                    "endpoint": "failed_runs_analysis",
                    "url": f"{self.base_url}/api/v1/executions",
                    "status_code": 200,
                    "available": True,
                    "analysis": analysis,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                        
        except Exception as e:
            logger.error(f"Exception in failed runs analysis: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Reached only when the executions could not be retrieved - see
        # get_workflow_executions_analysis for why we do not report zeros.
        return {
            "endpoint": "failed_runs_analysis",
            "url": f"{self.base_url}/api/v1/executions",
            "status_code": None,
            "available": False,
            "error": "executions data unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _analyze_workflow_executions(self, executions_list: List[Dict]) -> Dict:
        """
        Analyze executions to calculate comprehensive workflow execution statistics with time filtering
        """
        from datetime import datetime, timedelta, timezone
        import statistics
        
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_8h = now - timedelta(hours=8)
        
        # Group executions by workflow
        workflows_data = {}
        
        for execution in executions_list:
            workflow_id = execution.get('workflowId')
            if not workflow_id:
                continue
                
            if workflow_id not in workflows_data:
                workflows_data[workflow_id] = {
                    'workflow_name': self._resolve_workflow_name(execution),
                    'is_active': True,  # Assume active if we have executions
                    'last_execution': execution.get('startedAt', 'unknown'),
                    'executions_24h': [],
                    'executions_8h': [],
                    'all_executions': []
                }
            
            # Parse execution timestamp
            started_at_str = execution.get('startedAt')
            if started_at_str:
                try:
                    # Handle different timestamp formats
                    if started_at_str.endswith('Z'):
                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                    else:
                        started_at = datetime.fromisoformat(started_at_str)
                    
                    execution['parsed_started_at'] = started_at
                    
                    # Update last execution if this is more recent
                    try:
                        current_last = workflows_data[workflow_id]['last_execution']
                        if current_last != 'unknown':
                            current_last_dt = datetime.fromisoformat(current_last.replace('Z', '+00:00'))
                            if started_at > current_last_dt:
                                workflows_data[workflow_id]['last_execution'] = started_at_str
                        else:
                            workflows_data[workflow_id]['last_execution'] = started_at_str
                    except (ValueError, TypeError):
                        # If we can't parse the current last execution, update it
                        workflows_data[workflow_id]['last_execution'] = started_at_str
                    
                    # Categorize by time period
                    if started_at >= cutoff_24h:
                        workflows_data[workflow_id]['executions_24h'].append(execution)
                    if started_at >= cutoff_8h:
                        workflows_data[workflow_id]['executions_8h'].append(execution)
                    
                    workflows_data[workflow_id]['all_executions'].append(execution)
                    
                except (ValueError, TypeError):
                    # Skip executions with invalid timestamps
                    continue
        
        # Calculate statistics for each workflow
        workflow_stats = []
        total_workflows = len(workflows_data)
        workflows_with_executions = 0
        workflows_with_failures_24h = 0
        workflows_with_failures_8h = 0
        total_failures_24h = 0
        total_failures_8h = 0
        total_successful_24h = 0
        total_successful_8h = 0
        
        for workflow_id, data in workflows_data.items():
            workflow_name = data['workflow_name']
            is_active = data['is_active']
            last_execution = data['last_execution']
            executions_24h = data['executions_24h']
            executions_8h = data['executions_8h']
            
            # Calculate 24h statistics
            total_24h = len(executions_24h)
            failed_24h = len([e for e in executions_24h if e.get('status') in ['error', 'failed']])
            error_24h = len([e for e in executions_24h if e.get('status') == 'error'])
            successful_24h = len([e for e in executions_24h if e.get('status') == 'success'])
            success_rate_24h = (successful_24h / total_24h * 100) if total_24h > 0 else 100
            
            # Calculate 8h statistics
            total_8h = len(executions_8h)
            failed_8h = len([e for e in executions_8h if e.get('status') in ['error', 'failed']])
            error_8h = len([e for e in executions_8h if e.get('status') == 'error'])
            successful_8h = len([e for e in executions_8h if e.get('status') == 'success'])
            success_rate_8h = (successful_8h / total_8h * 100) if total_8h > 0 else 100
            
            # Calculate failure durations and percentiles for 24h and 8h
            failed_executions_24h = [e for e in executions_24h if e.get('status') in ['error', 'failed']]
            failed_executions_8h = [e for e in executions_8h if e.get('status') in ['error', 'failed']]
            
            failure_durations_24h = []
            failure_durations_8h = []
            recent_failures = []
            
            # Process 24h failures
            for execution in failed_executions_24h[:10]:  # Keep only recent failures
                started_at = execution.get('parsed_started_at')
                finished_at_str = execution.get('finishedAt')
                
                duration = 0
                if started_at and finished_at_str:
                    try:
                        if finished_at_str.endswith('Z'):
                            finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                        else:
                            finished_at = datetime.fromisoformat(finished_at_str)
                        duration = (finished_at - started_at).total_seconds()
                        failure_durations_24h.append(duration)
                    except (ValueError, TypeError):
                        pass
                
                # Extract error details
                error_data = execution.get('data', {}).get('resultData', {}).get('runData', {}).get('error', {})
                error_message = error_data.get('message', 'Unknown error') if error_data else 'Unknown error'
                error_node = error_data.get('node', {}).get('name', 'unknown') if error_data else 'unknown'
                
                recent_failures.append({
                    'execution_id': execution.get('id', 'unknown'),
                    'workflow_id': workflow_id,
                    'workflow_name': workflow_name,
                    'status': execution.get('status', 'error'),
                    'started_at': execution.get('startedAt', 'unknown'),
                    'finished_at': execution.get('finishedAt', 'unknown'),
                    'error_message': error_message,
                    'node_name': error_node,
                    'timestamp': execution.get('startedAt', 'unknown'),
                    'duration': duration
                })
            
            # Process 8h failures for separate percentiles
            for execution in failed_executions_8h:
                started_at = execution.get('parsed_started_at')
                finished_at_str = execution.get('finishedAt')
                
                if started_at and finished_at_str:
                    try:
                        if finished_at_str.endswith('Z'):
                            finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                        else:
                            finished_at = datetime.fromisoformat(finished_at_str)
                        duration = (finished_at - started_at).total_seconds()
                        failure_durations_8h.append(duration)
                    except (ValueError, TypeError):
                        pass
            
            # Calculate percentiles for 24h
            avg_duration_24h = statistics.mean(failure_durations_24h) if failure_durations_24h else 0
            p95_24h = statistics.quantiles(failure_durations_24h, n=20)[18] if len(failure_durations_24h) >= 20 else (max(failure_durations_24h) if failure_durations_24h else 0)
            p99_24h = statistics.quantiles(failure_durations_24h, n=100)[98] if len(failure_durations_24h) >= 100 else (max(failure_durations_24h) if failure_durations_24h else 0)
            
            # Calculate percentiles for 8h
            avg_duration_8h = statistics.mean(failure_durations_8h) if failure_durations_8h else 0
            p95_8h = statistics.quantiles(failure_durations_8h, n=20)[18] if len(failure_durations_8h) >= 20 else (max(failure_durations_8h) if failure_durations_8h else 0)
            p99_8h = statistics.quantiles(failure_durations_8h, n=100)[98] if len(failure_durations_8h) >= 100 else (max(failure_durations_8h) if failure_durations_8h else 0)
            
            workflow_stat = {
                'workflow_id': workflow_id,
                'workflow_name': workflow_name,
                'is_active': is_active,
                'last_execution': last_execution,
                'total_executions_24h': total_24h,
                'successful_executions_24h': successful_24h,
                'failed_executions_24h': failed_24h,
                'error_executions_24h': error_24h,
                'success_rate_24h': round(success_rate_24h, 2),
                'total_executions_8h': total_8h,
                'successful_executions_8h': successful_8h,
                'failed_executions_8h': failed_8h,
                'error_executions_8h': error_8h,
                'success_rate_8h': round(success_rate_8h, 2),
                'avg_failure_duration_24h': round(avg_duration_24h, 2),
                'avg_failure_duration_8h': round(avg_duration_8h, 2),
                'failure_duration_p95_24h': round(p95_24h, 2),
                'failure_duration_p99_24h': round(p99_24h, 2),
                'failure_duration_p95_8h': round(p95_8h, 2),
                'failure_duration_p99_8h': round(p99_8h, 2),
                'recent_failures': recent_failures
            }
            
            workflow_stats.append(workflow_stat)
            
            # Update totals
            if total_24h > 0 or total_8h > 0:
                workflows_with_executions += 1
            if failed_24h > 0:
                workflows_with_failures_24h += 1
            if failed_8h > 0:
                workflows_with_failures_8h += 1
            total_failures_24h += failed_24h
            total_failures_8h += failed_8h
            total_successful_24h += successful_24h
            total_successful_8h += successful_8h
        
        # Calculate overall success rates
        total_executions_24h = total_successful_24h + total_failures_24h
        total_executions_8h = total_successful_8h + total_failures_8h
        global_success_rate_24h = (total_successful_24h / total_executions_24h * 100) if total_executions_24h > 0 else 100
        global_success_rate_8h = (total_successful_8h / total_executions_8h * 100) if total_executions_8h > 0 else 100
        
        return {
            'total_workflows': total_workflows,
            'workflows_with_executions': workflows_with_executions,
            'workflows_with_failures_24h': workflows_with_failures_24h,
            'workflows_with_failures_8h': workflows_with_failures_8h,
            'global_success_rate_24h': round(global_success_rate_24h, 2),
            'global_success_rate_8h': round(global_success_rate_8h, 2),
            'total_failures_24h': total_failures_24h,
            'total_failures_8h': total_failures_8h,
            'workflows': workflow_stats
        }

    def _analyze_failed_runs(self, executions_list: List[Dict]) -> Dict:
        """
        Analyze executions to calculate failed runs statistics with time filtering
        """
        from datetime import datetime, timedelta, timezone
        import statistics
        
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_8h = now - timedelta(hours=8)
        
        # Group executions by workflow
        workflows_data = {}
        
        for execution in executions_list:
            workflow_id = execution.get('workflowId')
            if not workflow_id:
                continue
                
            if workflow_id not in workflows_data:
                workflows_data[workflow_id] = {
                    'workflow_name': self._resolve_workflow_name(execution),
                    'executions_24h': [],
                    'executions_8h': [],
                    'all_executions': []
                }
            
            # Parse execution timestamp
            started_at_str = execution.get('startedAt')
            if started_at_str:
                try:
                    # Handle different timestamp formats
                    if started_at_str.endswith('Z'):
                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                    else:
                        started_at = datetime.fromisoformat(started_at_str)
                    
                    execution['parsed_started_at'] = started_at
                    
                    # Categorize by time period
                    if started_at >= cutoff_24h:
                        workflows_data[workflow_id]['executions_24h'].append(execution)
                    if started_at >= cutoff_8h:
                        workflows_data[workflow_id]['executions_8h'].append(execution)
                    
                    workflows_data[workflow_id]['all_executions'].append(execution)
                    
                except (ValueError, TypeError):
                    # Skip executions with invalid timestamps
                    continue
        
        # Calculate statistics for each workflow
        workflow_stats = []
        total_workflows = len(workflows_data)
        workflows_with_failures = 0
        total_failures_24h = 0
        total_failures_8h = 0
        total_successful_24h = 0
        total_successful_8h = 0
        
        for workflow_id, data in workflows_data.items():
            workflow_name = data['workflow_name']
            executions_24h = data['executions_24h']
            executions_8h = data['executions_8h']
            
            # Calculate 24h statistics
            total_24h = len(executions_24h)
            failed_24h = len([e for e in executions_24h if e.get('status') in ['error', 'failed']])
            successful_24h = len([e for e in executions_24h if e.get('status') == 'success'])
            success_rate_24h = (successful_24h / total_24h * 100) if total_24h > 0 else 100
            
            # Calculate 8h statistics
            total_8h = len(executions_8h)
            failed_8h = len([e for e in executions_8h if e.get('status') in ['error', 'failed']])
            successful_8h = len([e for e in executions_8h if e.get('status') == 'success'])
            success_rate_8h = (successful_8h / total_8h * 100) if total_8h > 0 else 100
            
            # Calculate failure durations and percentiles
            failed_executions = [e for e in executions_24h if e.get('status') in ['error', 'failed']]
            failure_durations = []
            recent_failures = []
            
            for execution in failed_executions[:10]:  # Keep only recent failures
                started_at = execution.get('parsed_started_at')
                finished_at_str = execution.get('finishedAt')
                
                duration = 0
                if started_at and finished_at_str:
                    try:
                        if finished_at_str.endswith('Z'):
                            finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                        else:
                            finished_at = datetime.fromisoformat(finished_at_str)
                        duration = (finished_at - started_at).total_seconds()
                        failure_durations.append(duration)
                    except (ValueError, TypeError):
                        pass
                
                # Extract error details
                error_data = execution.get('data', {}).get('resultData', {}).get('runData', {}).get('error', {})
                error_message = error_data.get('message', 'Unknown error') if error_data else 'Unknown error'
                error_node = error_data.get('node', {}).get('name', 'unknown') if error_data else 'unknown'
                
                recent_failures.append({
                    'execution_id': execution.get('id', 'unknown'),
                    'workflow_id': workflow_id,
                    'workflow_name': workflow_name,
                    'status': execution.get('status', 'error'),
                    'started_at': execution.get('startedAt', 'unknown'),
                    'finished_at': execution.get('finishedAt', 'unknown'),
                    'error_message': error_message,
                    'error_node': error_node,
                    'duration': duration
                })
            
            # Calculate percentiles
            avg_duration = statistics.mean(failure_durations) if failure_durations else 0
            p95 = statistics.quantiles(failure_durations, n=20)[18] if len(failure_durations) >= 20 else (max(failure_durations) if failure_durations else 0)
            p99 = statistics.quantiles(failure_durations, n=100)[98] if len(failure_durations) >= 100 else (max(failure_durations) if failure_durations else 0)
            
            workflow_stat = {
                'workflow_id': workflow_id,
                'workflow_name': workflow_name,
                'total_executions_24h': total_24h,
                'failed_executions_24h': failed_24h,
                'successful_executions_24h': successful_24h,
                'success_rate_24h': round(success_rate_24h, 2),
                'total_executions_8h': total_8h,
                'failed_executions_8h': failed_8h,
                'successful_executions_8h': successful_8h,
                'success_rate_8h': round(success_rate_8h, 2),
                'recent_failures': recent_failures,
                'avg_failure_duration': round(avg_duration, 2),
                'failure_percentile_95': round(p95, 2),
                'failure_percentile_99': round(p99, 2)
            }
            
            workflow_stats.append(workflow_stat)
            
            # Update totals
            if failed_24h > 0:
                workflows_with_failures += 1
            total_failures_24h += failed_24h
            total_failures_8h += failed_8h
            total_successful_24h += successful_24h
            total_successful_8h += successful_8h
        
        # Calculate overall success rates
        total_executions_24h = total_successful_24h + total_failures_24h
        total_executions_8h = total_successful_8h + total_failures_8h
        overall_success_rate_24h = (total_successful_24h / total_executions_24h * 100) if total_executions_24h > 0 else 100
        overall_success_rate_8h = (total_successful_8h / total_executions_8h * 100) if total_executions_8h > 0 else 100
        
        return {
            'total_workflows': total_workflows,
            'workflows_with_failures': workflows_with_failures,
            'total_failures_24h': total_failures_24h,
            'total_failures_8h': total_failures_8h,
            'overall_success_rate_24h': round(overall_success_rate_24h, 2),
            'overall_success_rate_8h': round(overall_success_rate_8h, 2),
            'workflows': workflow_stats
        }

    async def get_webhooks(self) -> Dict:
        """Get n8n webhooks data"""
        endpoints = [
            "/api/v1/webhooks",
            "/rest/webhooks",
            "/api/webhooks",
            "/webhooks"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying to access webhooks API: {url}")
                
                headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
                if self.api_key:
                    headers['X-N8N-API-KEY'] = self.api_key
                elif self.username and self.password:
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                
                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"Webhooks API response status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.debug(f"Response content-type: {content_type}")
                        if 'application/json' in content_type:
                            webhooks_data = await response.json()
                            logger.debug(f"Webhooks data received: {len(webhooks_data.get('data', []))} webhooks")
                            return {
                                "endpoint": "webhooks",
                                "url": url,
                                "status_code": response.status,
                                "available": True,
                                "webhooks": webhooks_data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            text_data = await response.text()
                            logger.debug(f"Non-JSON response received (length: {len(text_data)})")
                            if '<html' in text_data.lower():
                                logger.warning(f"Received HTML response from {url}, likely not the correct API endpoint")
                                continue
                    elif response.status == 401:
                        logger.warning(f"Authentication failed for {url}")
                        continue
                    else:
                        logger.warning(f"Webhooks API returned status {response.status} for {url}")
                        continue
            except Exception as e:
                logger.debug(f"Error accessing {url}: {e}")
                continue
        
        return {
            "endpoint": "webhooks",
            "url": "multiple_endpoints_tried",
            "status_code": None,
            "available": False,
            "error": "All webhooks API endpoints failed",
            "webhooks": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_credentials(self) -> Dict:
        """Get n8n credentials data (without sensitive values)"""
        endpoints = [
            "/api/v1/credentials",
            "/rest/credentials",
            "/api/credentials",
            "/credentials"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying to access credentials API: {url}")
                
                headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
                if self.api_key:
                    headers['X-N8N-API-KEY'] = self.api_key
                elif self.username and self.password:
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                
                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"Credentials API response status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.debug(f"Response content-type: {content_type}")
                        if 'application/json' in content_type:
                            credentials_data = await response.json()
                            logger.debug(f"Credentials data received: {len(credentials_data.get('data', []))} credentials")
                            return {
                                "endpoint": "credentials",
                                "url": url,
                                "status_code": response.status,
                                "available": True,
                                "credentials": credentials_data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            text_data = await response.text()
                            logger.debug(f"Non-JSON response received (length: {len(text_data)})")
                            if '<html' in text_data.lower():
                                logger.warning(f"Received HTML response from {url}, likely not the correct API endpoint")
                                continue
                    elif response.status == 401:
                        logger.warning(f"Authentication failed for {url}")
                        continue
                    else:
                        logger.warning(f"Credentials API returned status {response.status} for {url}")
                        continue
            except Exception as e:
                logger.debug(f"Error accessing {url}: {e}")
                continue
        
        return {
            "endpoint": "credentials",
            "url": "multiple_endpoints_tried",
            "status_code": None,
            "available": False,
            "error": "All credentials API endpoints failed",
            "credentials": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_users(self) -> Dict:
        """
        Get n8n users data using API v1
        GET /api/v1/users?limit=250&includeRole=true
        """
        try:
            # Use API v1 endpoint with proper parameters
            url = f"{self.base_url}/api/v1/users"
            params = {
                'limit': 250,  # Maximum allowed
                'includeRole': 'true'  # Include user roles
            }
            
            logger.debug(f"Accessing users API: {url} with params: {params}")
            
            headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
            if self.api_key:
                headers['X-N8N-API-KEY'] = self.api_key
                logger.debug("Using API Key authentication for users")
            elif self.username and self.password:
                import base64
                credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
                logger.debug("Using Basic authentication for users")
            
            async with self.session.get(url, headers=headers, params=params) as response:
                logger.debug(f"Users API response status: {response.status}")
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        users_data = await response.json()
                        users_list = users_data.get('data', [])
                        logger.info(f"Successfully retrieved {len(users_list)} users")
                        
                        return {
                            "endpoint": "users",
                            "url": url,
                            "status_code": response.status,
                            "available": True,
                            "users": users_data,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    else:
                        logger.error(f"Unexpected content-type: {content_type}")
                elif response.status == 401:
                    logger.error("Authentication failed for users API - check API key")
                else:
                    logger.error(f"Users API returned status {response.status}")
                    error_text = await response.text()
                    logger.debug(f"Error response: {error_text[:200]}")
                    
        except Exception as e:
            logger.error(f"Exception accessing users API: {e}")
        
        return {
            "endpoint": "users",
            "url": f"{self.base_url}/api/v1/users",
            "status_code": None,
            "available": False,
            "error": "Failed to retrieve users",
            "users": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_tags(self) -> Dict:
        """Get n8n tags data"""
        endpoints = [
            "/api/v1/tags",
            "/rest/tags",
            "/api/tags"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying to access tags API: {url}")
                
                headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
                if self.api_key:
                    headers['X-N8N-API-KEY'] = self.api_key
                elif self.username and self.password:
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                
                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"Tags API response status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.debug(f"Response content-type: {content_type}")
                        if 'application/json' in content_type:
                            tags_data = await response.json()
                            logger.debug(f"Tags data received: {len(tags_data.get('data', []))} tags")
                            return {
                                "endpoint": "tags",
                                "url": url,
                                "status_code": response.status,
                                "available": True,
                                "tags": tags_data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            text_data = await response.text()
                            logger.debug(f"Non-JSON response received (length: {len(text_data)})")
                            if '<html' in text_data.lower():
                                logger.warning(f"Received HTML response from {url}, likely not the correct API endpoint")
                                continue
                    elif response.status == 401:
                        logger.warning(f"Authentication failed for {url}")
                        continue
                    else:
                        logger.warning(f"Tags API returned status {response.status} for {url}")
                        continue
            except Exception as e:
                logger.debug(f"Error accessing {url}: {e}")
                continue
        
        return {
            "endpoint": "tags",
            "url": "multiple_endpoints_tried",
            "status_code": None,
            "available": False,
            "error": "All tags API endpoints failed",
            "tags": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_variables(self) -> Dict:
        """Get n8n variables data"""
        endpoints = [
            "/api/v1/variables",
            "/rest/variables",
            "/api/variables"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying to access variables API: {url}")
                
                headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
                if self.api_key:
                    headers['X-N8N-API-KEY'] = self.api_key
                elif self.username and self.password:
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                
                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"Variables API response status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.debug(f"Response content-type: {content_type}")
                        if 'application/json' in content_type:
                            variables_data = await response.json()
                            logger.debug(f"Variables data received: {len(variables_data.get('data', []))} variables")
                            return {
                                "endpoint": "variables",
                                "url": url,
                                "status_code": response.status,
                                "available": True,
                                "variables": variables_data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            text_data = await response.text()
                            logger.debug(f"Non-JSON response received (length: {len(text_data)})")
                            if '<html' in text_data.lower():
                                logger.warning(f"Received HTML response from {url}, likely not the correct API endpoint")
                                continue
                    elif response.status == 401:
                        logger.warning(f"Authentication failed for {url}")
                        continue
                    else:
                        logger.warning(f"Variables API returned status {response.status} for {url}")
                        continue
            except Exception as e:
                logger.debug(f"Error accessing {url}: {e}")
                continue
        
        return {
            "endpoint": "variables",
            "url": "multiple_endpoints_tried",
            "status_code": None,
            "available": False,
            "error": "All variables API endpoints failed",
            "variables": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_projects(self) -> Dict:
        """Get n8n projects data"""
        endpoints = [
            "/api/v1/projects",
            "/rest/projects",
            "/api/projects"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                logger.debug(f"Trying to access projects API: {url}")
                
                headers = {'User-Agent': 'n8n-monitor-agent/1.0'}
                if self.api_key:
                    headers['X-N8N-API-KEY'] = self.api_key
                elif self.username and self.password:
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers['Authorization'] = f'Basic {credentials}'
                
                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"Projects API response status: {response.status}")
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        logger.debug(f"Response content-type: {content_type}")
                        if 'application/json' in content_type:
                            projects_data = await response.json()
                            logger.debug(f"Projects data received: {len(projects_data.get('data', []))} projects")
                            return {
                                "endpoint": "projects",
                                "url": url,
                                "status_code": response.status,
                                "available": True,
                                "projects": projects_data,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            text_data = await response.text()
                            logger.debug(f"Non-JSON response received (length: {len(text_data)})")
                            if '<html' in text_data.lower():
                                logger.warning(f"Received HTML response from {url}, likely not the correct API endpoint")
                                continue
                    elif response.status == 401:
                        logger.warning(f"Authentication failed for {url}")
                        continue
                    else:
                        logger.warning(f"Projects API returned status {response.status} for {url}")
                        continue
            except Exception as e:
                logger.debug(f"Error accessing {url}: {e}")
                continue
        
        return {
            "endpoint": "projects",
            "url": "multiple_endpoints_tried",
            "status_code": None,
            "available": False,
            "error": "All projects API endpoints failed",
            "projects": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict:
        """Parse Prometheus metrics format into structured data"""
        metrics = {}
        lines = metrics_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            # Parse metric line (format: name{labels} value)
            if ' ' in line:
                parts = line.rsplit(' ', 1)
                if len(parts) == 2:
                    metric_part = parts[0]
                    value_part = parts[1]
                    
                    try:
                        value = float(value_part)
                        
                        # Extract metric name and labels
                        if '{' in metric_part and '}' in metric_part:
                            name = metric_part.split('{')[0]
                            labels_part = metric_part.split('{')[1].rstrip('}')
                            labels = {}
                            if labels_part:
                                for label_pair in labels_part.split(','):
                                    if '=' in label_pair:
                                        key, val = label_pair.split('=', 1)
                                        labels[key.strip()] = val.strip().strip('"')
                        else:
                            name = metric_part
                            labels = {}
                        
                        if name not in metrics:
                            metrics[name] = []
                        metrics[name].append({
                            'value': value,
                            'labels': labels
                        })
                    except ValueError:
                        continue
        
        return metrics

def output_checkmk_format(results: Dict):
    """Output results in CheckMK format with separate sections"""
    
    # Health Check Section
    if 'healthz' in results:
        healthz_data = results['healthz']
        print("<<<n8n_healthz>>>")
        status = "OK" if healthz_data.get('healthy', False) else "CRIT"
        status_code = healthz_data.get('status_code', 0)
        response_time = healthz_data.get('response_time', 0)
        print(f"{status};{status_code};{response_time}")
    
    # Readiness Check Section
    if 'readiness' in results:
        readiness_data = results['readiness']
        print("<<<n8n_readiness>>>")
        status = "OK" if readiness_data.get('ready', False) else "CRIT"
        status_code = readiness_data.get('status_code', 0)
        response_time = readiness_data.get('response_time', 0)
        print(f"{status};{status_code};{response_time}")
    
    # Metrics Section
    if 'metrics' in results and results['metrics'].get('available', False):
        metrics_data = results['metrics']
        print("<<<n8n_metrics>>>")
        
        # Process metrics
        metrics = metrics_data.get('metrics', {})
        
        # System metrics
        if 'n8n_process_resident_memory_bytes' in metrics:
            memory = metrics['n8n_process_resident_memory_bytes'][0]['value']
            print(f"memory;{memory}")
        
        if 'n8n_process_cpu_seconds_total' in metrics:
            cpu = metrics['n8n_process_cpu_seconds_total'][0]['value']
            print(f"cpu;{cpu}")
        
        if 'n8n_process_open_fds' in metrics:
            fds = metrics['n8n_process_open_fds'][0]['value']
            print(f"fds;{fds}")
        
        # Node.js metrics
        if 'n8n_nodejs_heap_size_used_bytes' in metrics:
            heap_used = metrics['n8n_nodejs_heap_size_used_bytes'][0]['value']
            print(f"heap_used;{heap_used}")
        
        if 'n8n_nodejs_heap_size_total_bytes' in metrics:
            heap_total = metrics['n8n_nodejs_heap_size_total_bytes'][0]['value']
            print(f"heap_total;{heap_total}")
        
        if 'n8n_nodejs_eventloop_lag_seconds' in metrics:
            eventloop_lag = metrics['n8n_nodejs_eventloop_lag_seconds'][0]['value']
            print(f"eventloop_lag;{eventloop_lag}")
        
        # n8n specific metrics
        if 'n8n_active_workflow_count' in metrics:
            workflows = metrics['n8n_active_workflow_count'][0]['value']
            print(f"workflows;{workflows}")
        
        # Version info
        if 'n8n_version_info' in metrics:
            version_info = metrics['n8n_version_info'][0]['labels']
            version = version_info.get('version', 'unknown')
            print(f"version;{version}")
        
        if 'n8n_nodejs_version_info' in metrics:
            nodejs_info = metrics['n8n_nodejs_version_info'][0]['labels']
            nodejs_version = nodejs_info.get('version', 'unknown')
            print(f"nodejs_version;{nodejs_version}")
        
        # Additional system metrics
        if 'n8n_process_resident_memory_bytes' in metrics:
            memory_mb = metrics['n8n_process_resident_memory_bytes'][0]['value'] / (1024 * 1024)
            print(f"memory_mb;{memory_mb:.2f}")
        
        if 'n8n_nodejs_heap_size_used_bytes' in metrics and 'n8n_nodejs_heap_size_total_bytes' in metrics:
            heap_used = metrics['n8n_nodejs_heap_size_used_bytes'][0]['value']
            heap_total = metrics['n8n_nodejs_heap_size_total_bytes'][0]['value']
            heap_percent = (heap_used / heap_total) * 100 if heap_total > 0 else 0
            print(f"heap_percent;{heap_percent:.2f}")
        
        # Event loop lag in milliseconds
        if 'n8n_nodejs_eventloop_lag_seconds' in metrics:
            eventloop_lag_ms = metrics['n8n_nodejs_eventloop_lag_seconds'][0]['value'] * 1000
            print(f"eventloop_lag_ms;{eventloop_lag_ms:.2f}")
        
        # GC metrics
        if 'n8n_nodejs_gc_duration_seconds_count' in metrics:
            gc_counts = metrics['n8n_nodejs_gc_duration_seconds_count']
            total_gc = sum(item['value'] for item in gc_counts)
            print(f"gc_total;{total_gc}")
        
        # Active resources
        if 'n8n_nodejs_active_resources_total' in metrics:
            active_resources = metrics['n8n_nodejs_active_resources_total'][0]['value']
            print(f"active_resources;{active_resources}")
        
        if 'n8n_nodejs_active_handles_total' in metrics:
            active_handles = metrics['n8n_nodejs_active_handles_total'][0]['value']
            print(f"active_handles;{active_handles}")
        
        # Additional metrics from Prometheus data
        # Filter out bucket metrics and only include sum metrics for GC duration
        for metric_name, metric_data in metrics.items():
            if metric_name.startswith('n8n_') and metric_name not in [
                'n8n_process_resident_memory_bytes', 'n8n_process_cpu_seconds_total',
                'n8n_process_open_fds', 'n8n_nodejs_heap_size_used_bytes',
                'n8n_nodejs_heap_size_total_bytes', 'n8n_nodejs_eventloop_lag_seconds',
                'n8n_active_workflow_count', 'n8n_version_info', 'n8n_nodejs_version_info',
                'n8n_nodejs_gc_duration_seconds_count', 'n8n_nodejs_active_resources_total',
                'n8n_nodejs_active_handles_total'
            ]:
                # Skip bucket metrics (histogram buckets) - we only want sum metrics
                if 'bucket' in metric_name.lower():
                    continue
                
                # For GC duration, only include sum metrics, not bucket or count
                if 'gc_duration' in metric_name.lower():
                    if 'sum' not in metric_name.lower():
                        continue
                
                # Add any other n8n metrics we haven't covered
                for item in metric_data:
                    value = item['value']
                    labels = item.get('labels', {})
                    if labels:
                        # Create a unique key with labels
                        label_str = '_'.join([f"{k}_{v}" for k, v in labels.items()])
                        print(f"{metric_name}_{label_str};{value}")
                    else:
                        print(f"{metric_name};{value}")
    
    # Executions Section
    if 'executions' in results and results['executions'].get('available', False):
        executions_data = results['executions']
        print("<<<n8n_executions>>>")
        
        executions = executions_data.get('executions', {})
        if 'data' in executions:
            executions_list = executions['data']
            
            # Count executions by status
            total_executions = len(executions_list)
            successful_executions = len([e for e in executions_list if e.get('finished', False) and e.get('data', {}).get('resultData', {}).get('runData', {}).get('error', None) is None])
            failed_executions = len([e for e in executions_list if e.get('finished', False) and e.get('data', {}).get('resultData', {}).get('runData', {}).get('error', None) is not None])
            running_executions = len([e for e in executions_list if not e.get('finished', False)])
            
            print(f"total;{total_executions}")
            print(f"successful;{successful_executions}")
            print(f"failed;{failed_executions}")
            print(f"running;{running_executions}")
            
            # Recent failures (last 10)
            recent_failures = [e for e in executions_list if e.get('finished', False) and e.get('data', {}).get('resultData', {}).get('runData', {}).get('error', None) is not None][:10]
            
            workflow_names = results.get('workflow_names', {})
            for execution in recent_failures:
                execution_id = execution.get('id', 'unknown')
                workflow_name = (execution.get('workflowData') or {}).get('name') or workflow_names.get(
                    str(execution.get('workflowId')), 'unknown'
                )
                started_at = execution.get('startedAt', 'unknown')
                finished_at = execution.get('finishedAt', 'unknown')
                
                # Get error details
                error_data = execution.get('data', {}).get('resultData', {}).get('runData', {}).get('error', {})
                error_message = error_data.get('message', 'Unknown error') if error_data else 'Unknown error'
                error_node = error_data.get('node', {}).get('name', 'unknown') if error_data else 'unknown'
                
                print(f"failure;{execution_id};{workflow_name};{error_node};{error_message};{started_at};{finished_at}")
        else:
            print("total;0")
            print("successful;0")
            print("failed;0")
            print("running;0")
    
    # Workflows Section
    if 'workflows' in results and results['workflows'].get('available', False):
        workflows_data = results['workflows']
        print("<<<n8n_workflows>>>")
        
        workflows = workflows_data.get('workflows', {})
        if 'data' in workflows:
            workflows_list = workflows['data']
            
            total_workflows = len(workflows_list)
            active_workflows = len([w for w in workflows_list if w.get('active', False)])
            inactive_workflows = total_workflows - active_workflows
            
            # Calculate additional statistics
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            recently_updated = 0
            with_tags = 0
            without_tags = 0
            total_nodes = 0
            total_connections = 0
            most_complex_workflow = None
            most_complex_count = 0
            least_complex_workflow = None
            least_complex_count = float('inf')
            
            for workflow in workflows_list:
                # Check if updated in last 24h
                updated_at_str = workflow.get('updatedAt', '')
                if updated_at_str and updated_at_str != 'unknown':
                    try:
                        # Parse ISO format timestamp
                        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                        if (now - updated_at).total_seconds() < 86400:  # 24 hours
                            recently_updated += 1
                    except (ValueError, AttributeError):
                        pass
                
                # Check tags
                tags = workflow.get('tags', [])
                if tags and len(tags) > 0:
                    with_tags += 1
                else:
                    without_tags += 1
                
                # Count nodes and connections
                nodes = workflow.get('nodes', [])
                connections = workflow.get('connections', {})
                nodes_count = len(nodes) if isinstance(nodes, list) else 0
                
                # Calculate connections count
                connections_count = 0
                if isinstance(connections, dict):
                    for node_connections in connections.values():
                        if isinstance(node_connections, dict):
                            for connection_list in node_connections.values():
                                if isinstance(connection_list, list):
                                    for conn_array in connection_list:
                                        if isinstance(conn_array, list):
                                            connections_count += len(conn_array)
                
                total_nodes += nodes_count
                total_connections += connections_count
                
                # Track most/least complex workflows
                complexity = nodes_count + connections_count
                workflow_name = workflow.get('name', 'unknown')
                
                if complexity > most_complex_count:
                    most_complex_count = complexity
                    most_complex_workflow = f"{workflow_name} ({nodes_count}N/{connections_count}C)"
                
                if complexity < least_complex_count and complexity > 0:
                    least_complex_count = complexity
                    least_complex_workflow = f"{workflow_name} ({nodes_count}N/{connections_count}C)"
            
            # Calculate averages
            avg_nodes = total_nodes / total_workflows if total_workflows > 0 else 0
            avg_connections = total_connections / total_workflows if total_workflows > 0 else 0
            
            # Output statistics
            print(f"total;{total_workflows}")
            print(f"active;{active_workflows}")
            print(f"inactive;{inactive_workflows}")
            print(f"recently_updated;{recently_updated}")
            print(f"with_tags;{with_tags}")
            print(f"without_tags;{without_tags}")
            print(f"avg_nodes;{avg_nodes:.2f}")
            print(f"avg_connections;{avg_connections:.2f}")
            
            if most_complex_workflow:
                print(f"most_complex;{most_complex_workflow}")
            if least_complex_workflow:
                print(f"least_complex;{least_complex_workflow}")
            
            # Workflow details
            for workflow in workflows_list:
                workflow_id = workflow.get('id', 'unknown')
                workflow_name = workflow.get('name', 'unknown')
                is_active = workflow.get('active', False)
                created_at = workflow.get('createdAt', 'unknown')
                updated_at = workflow.get('updatedAt', 'unknown')
                
                # Extract tags
                tags = workflow.get('tags', [])
                tags_str = ','.join([str(tag.get('name', tag) if isinstance(tag, dict) else tag) for tag in tags])
                
                # Count nodes and connections
                nodes = workflow.get('nodes', [])
                nodes_count = len(nodes) if isinstance(nodes, list) else 0
                
                connections = workflow.get('connections', {})
                connections_count = 0
                if isinstance(connections, dict):
                    for node_connections in connections.values():
                        if isinstance(node_connections, dict):
                            for connection_list in node_connections.values():
                                if isinstance(connection_list, list):
                                    for conn_array in connection_list:
                                        if isinstance(conn_array, list):
                                            connections_count += len(conn_array)
                
                # Get execution statistics
                execution_stats = workflow.get('execution_stats', {})
                total_executions = execution_stats.get('total_executions', 0)
                successful_executions = execution_stats.get('successful_executions', 0)
                failed_executions = execution_stats.get('failed_executions', 0)
                error_executions = execution_stats.get('error_executions', 0)
                waiting_executions = execution_stats.get('waiting_executions', 0)
                running_executions = execution_stats.get('running_executions', 0)
                success_rate = execution_stats.get('success_rate', 0)
                
                # Get 24h and 8h statistics
                total_executions_24h = execution_stats.get('total_executions_24h', 0)
                successful_executions_24h = execution_stats.get('successful_executions_24h', 0)
                failed_executions_24h = execution_stats.get('failed_executions_24h', 0)
                success_rate_24h = execution_stats.get('success_rate_24h', 0)
                
                total_executions_8h = execution_stats.get('total_executions_8h', 0)
                successful_executions_8h = execution_stats.get('successful_executions_8h', 0)
                failed_executions_8h = execution_stats.get('failed_executions_8h', 0)
                success_rate_8h = execution_stats.get('success_rate_8h', 0)
                
                # Get failed runs analysis
                avg_failure_duration = execution_stats.get('avg_failure_duration', 0)
                failure_duration_p95 = execution_stats.get('failure_duration_p95', 0)
                failure_duration_p99 = execution_stats.get('failure_duration_p99', 0)
                recent_failures = execution_stats.get('recent_failures', [])
                recent_failures_json = json.dumps(recent_failures) if recent_failures else '[]'
                
                # Extended format with failed runs analysis
                # Format: workflow;id;name;active;created;updated;tags;nodes;connections;total_executions;successful;failed;error;waiting;running;success_rate;total_24h;successful_24h;failed_24h;success_rate_24h;total_8h;successful_8h;failed_8h;success_rate_8h;avg_failure_duration;p95_failure_duration;p99_failure_duration;recent_failures
                print(f"workflow;{workflow_id};{workflow_name};{is_active};{created_at};{updated_at};{tags_str};{nodes_count};{connections_count};{total_executions};{successful_executions};{failed_executions};{error_executions};{waiting_executions};{running_executions};{success_rate};{total_executions_24h};{successful_executions_24h};{failed_executions_24h};{success_rate_24h};{total_executions_8h};{successful_executions_8h};{failed_executions_8h};{success_rate_8h};{avg_failure_duration};{failure_duration_p95};{failure_duration_p99};{recent_failures_json}")
        else:
            print("total;0")
            print("active;0")
            print("inactive;0")
            print("recently_updated;0")
            print("with_tags;0")
            print("without_tags;0")
            print("avg_nodes;0")
            print("avg_connections;0")
    
    # Webhooks and Credentials sections removed
    # These endpoints are not available in n8n Public API v1
    # They require special authentication/permissions not documented in public API
    
    # Users Section
    if 'users' in results and results['users'].get('available', False):
        users_data = results['users']
        print("<<<n8n_users>>>")
        
        users = users_data.get('users', {})
        if 'data' in users:
            users_list = users['data']
            
            total_users = len(users_list)
            pending_users = len([u for u in users_list if u.get('isPending', False)])
            active_users = total_users - pending_users
            
            print(f"total;{total_users}")
            print(f"active;{active_users}")
            print(f"pending;{pending_users}")
            
            # User details
            for user in users_list:
                user_id = user.get('id', 'unknown')
                email = user.get('email', 'unknown')
                first_name = user.get('firstName', 'unknown')
                last_name = user.get('lastName', 'unknown')
                is_pending = user.get('isPending', False)
                role = user.get('role', 'unknown')
                created_at = user.get('createdAt', 'unknown')
                
                print(f"user;{user_id};{email};{first_name};{last_name};{is_pending};{role};{created_at}")
        else:
            print("total;0")
            print("active;0")
            print("pending;0")
    
    # Tags Section
    if 'tags' in results and results['tags'].get('available', False):
        tags_data = results['tags']
        print("<<<n8n_tags>>>")
        
        tags = tags_data.get('tags', {})
        if 'data' in tags:
            tags_list = tags['data']
            
            total_tags = len(tags_list)
            
            print(f"total;{total_tags}")
            
            # Tag details
            for tag in tags_list:
                tag_id = tag.get('id', 'unknown')
                tag_name = tag.get('name', 'unknown')
                created_at = tag.get('createdAt', 'unknown')
                updated_at = tag.get('updatedAt', 'unknown')
                
                print(f"tag;{tag_id};{tag_name};{created_at};{updated_at}")
        else:
            print("total;0")
    
    # Variables Section
    if 'variables' in results and results['variables'].get('available', False):
        variables_data = results['variables']
        print("<<<n8n_variables>>>")
        
        variables = variables_data.get('variables', {})
        if 'data' in variables:
            variables_list = variables['data']
            
            total_variables = len(variables_list)
            
            print(f"total;{total_variables}")
            
            # Variable details (without sensitive values)
            for variable in variables_list:
                variable_id = variable.get('id', 'unknown')
                variable_key = variable.get('key', 'unknown')
                variable_type = variable.get('type', 'unknown')
                created_at = variable.get('createdAt', 'unknown')
                updated_at = variable.get('updatedAt', 'unknown')
                
                print(f"variable;{variable_id};{variable_key};{variable_type};{created_at};{updated_at}")
        else:
            print("total;0")
    
    # Projects Section
    if 'projects' in results and results['projects'].get('available', False):
        projects_data = results['projects']
        print("<<<n8n_projects>>>")
        
        projects = projects_data.get('projects', {})
        if 'data' in projects:
            projects_list = projects['data']
            
            total_projects = len(projects_list)
            
            print(f"total;{total_projects}")
            
            # Project details
            for project in projects_list:
                project_id = project.get('id', 'unknown')
                project_name = project.get('name', 'unknown')
                created_at = project.get('createdAt', 'unknown')
                updated_at = project.get('updatedAt', 'unknown')
                
                print(f"project;{project_id};{project_name};{created_at};{updated_at}")
        else:
            print("total;0")
    
    # Workflow Executions Analysis Section
    if 'workflow_executions_analysis' in results and results['workflow_executions_analysis'].get('available', False):
        workflow_executions_data = results['workflow_executions_analysis']
        print("<<<n8n_workflow_executions>>>")
        
        analysis = workflow_executions_data.get('analysis', {})
        if analysis:
            total_workflows = analysis.get('total_workflows', 0)
            workflows_with_executions = analysis.get('workflows_with_executions', 0)
            workflows_with_failures_24h = analysis.get('workflows_with_failures_24h', 0)
            workflows_with_failures_8h = analysis.get('workflows_with_failures_8h', 0)
            global_success_rate_24h = analysis.get('global_success_rate_24h', 0.0)
            global_success_rate_8h = analysis.get('global_success_rate_8h', 0.0)
            total_failures_24h = analysis.get('total_failures_24h', 0)
            total_failures_8h = analysis.get('total_failures_8h', 0)
            
            # Global statistics
            print(f"total_workflows;{total_workflows}")
            print(f"workflows_with_executions;{workflows_with_executions}")
            print(f"workflows_with_failures_24h;{workflows_with_failures_24h}")
            print(f"workflows_with_failures_8h;{workflows_with_failures_8h}")
            print(f"global_success_rate_24h;{global_success_rate_24h}")
            print(f"global_success_rate_8h;{global_success_rate_8h}")
            print(f"total_failures_24h;{total_failures_24h}")
            print(f"total_failures_8h;{total_failures_8h}")
            
            # Workflow details
            workflows = analysis.get('workflows', [])
            for workflow in workflows:
                workflow_id = workflow.get('workflow_id', 'unknown')
                workflow_name = workflow.get('workflow_name', 'unknown')
                is_active = workflow.get('is_active', True)
                last_execution = workflow.get('last_execution', 'unknown')
                
                # 24h statistics
                total_24h = workflow.get('total_executions_24h', 0)
                successful_24h = workflow.get('successful_executions_24h', 0)
                failed_24h = workflow.get('failed_executions_24h', 0)
                error_24h = workflow.get('error_executions_24h', 0)
                success_rate_24h = workflow.get('success_rate_24h', 0.0)
                
                # 8h statistics
                total_8h = workflow.get('total_executions_8h', 0)
                successful_8h = workflow.get('successful_executions_8h', 0)
                failed_8h = workflow.get('failed_executions_8h', 0)
                error_8h = workflow.get('error_executions_8h', 0)
                success_rate_8h = workflow.get('success_rate_8h', 0.0)
                
                # Performance metrics
                avg_failure_duration_24h = workflow.get('avg_failure_duration_24h', 0.0)
                avg_failure_duration_8h = workflow.get('avg_failure_duration_8h', 0.0)
                failure_duration_p95_24h = workflow.get('failure_duration_p95_24h', 0.0)
                failure_duration_p99_24h = workflow.get('failure_duration_p99_24h', 0.0)
                failure_duration_p95_8h = workflow.get('failure_duration_p95_8h', 0.0)
                failure_duration_p99_8h = workflow.get('failure_duration_p99_8h', 0.0)
                
                # Recent failures
                recent_failures = workflow.get('recent_failures', [])
                recent_failures_json = json.dumps(recent_failures) if recent_failures else '[]'
                
                print(f"workflow_execution;{workflow_id};{workflow_name};{is_active};{last_execution};{total_24h};{successful_24h};{failed_24h};{error_24h};{success_rate_24h};{total_8h};{successful_8h};{failed_8h};{error_8h};{success_rate_8h};{avg_failure_duration_24h};{avg_failure_duration_8h};{failure_duration_p95_24h};{failure_duration_p99_24h};{failure_duration_p95_8h};{failure_duration_p99_8h};{recent_failures_json}")
        else:
            print("total_workflows;0")
            print("workflows_with_executions;0")
            print("workflows_with_failures_24h;0")
            print("workflows_with_failures_8h;0")
            print("global_success_rate_24h;100.0")
            print("global_success_rate_8h;100.0")
            print("total_failures_24h;0")
            print("total_failures_8h;0")
    
    # Failed Runs Analysis Section
    if 'failed_runs_analysis' in results and results['failed_runs_analysis'].get('available', False):
        failed_runs_data = results['failed_runs_analysis']
        print("<<<n8n_failed_runs>>>")
        
        analysis = failed_runs_data.get('analysis', {})
        if analysis:
            total_workflows = analysis.get('total_workflows', 0)
            workflows_with_failures = analysis.get('workflows_with_failures', 0)
            total_failures_24h = analysis.get('total_failures_24h', 0)
            total_failures_8h = analysis.get('total_failures_8h', 0)
            success_rate_24h = analysis.get('overall_success_rate_24h', 0.0)
            success_rate_8h = analysis.get('overall_success_rate_8h', 0.0)
            
            # Summary line
            print(f"summary;{total_workflows};{workflows_with_failures};{total_failures_24h};{total_failures_8h};{success_rate_24h};{success_rate_8h}")
            
            # Workflow details
            workflows = analysis.get('workflows', [])
            for workflow in workflows:
                workflow_id = workflow.get('workflow_id', 'unknown')
                workflow_name = workflow.get('workflow_name', 'unknown')
                total_24h = workflow.get('total_executions_24h', 0)
                failed_24h = workflow.get('failed_executions_24h', 0)
                success_24h = workflow.get('successful_executions_24h', 0)
                rate_24h = workflow.get('success_rate_24h', 0.0)
                total_8h = workflow.get('total_executions_8h', 0)
                failed_8h = workflow.get('failed_executions_8h', 0)
                success_8h = workflow.get('successful_executions_8h', 0)
                rate_8h = workflow.get('success_rate_8h', 0.0)
                avg_duration = workflow.get('avg_failure_duration', 0.0)
                p95 = workflow.get('failure_percentile_95', 0.0)
                p99 = workflow.get('failure_percentile_99', 0.0)
                recent_failures_count = len(workflow.get('recent_failures', []))
                
                print(f"workflow;{workflow_id};{workflow_name};{total_24h};{failed_24h};{success_24h};{rate_24h};{total_8h};{failed_8h};{success_8h};{rate_8h};{avg_duration};{p95};{p99};{recent_failures_count}")
                
                # Recent failures details
                recent_failures = workflow.get('recent_failures', [])
                for failure in recent_failures:
                    execution_id = failure.get('execution_id', 'unknown')
                    error_node = failure.get('error_node', 'unknown')
                    error_message = failure.get('error_message', 'Unknown error')
                    started_at = failure.get('started_at', 'unknown')
                    finished_at = failure.get('finished_at', 'unknown')
                    duration = failure.get('duration', 0.0)
                    
                    print(f"failure;{workflow_id};{execution_id};{workflow_name};{error_node};{error_message};{started_at};{finished_at};{duration}")
        else:
            print("summary;0;0;0;0;100.0;100.0")
    
    # API Status Section
    print("<<<n8n_api_status>>>")
    api_status = {
        'healthz': 'OK' if 'healthz' in results and results['healthz'].get('healthy', False) else 'FAIL',
        'readiness': 'OK' if 'readiness' in results and results['readiness'].get('ready', False) else 'FAIL',
        'metrics': 'OK' if 'metrics' in results and results['metrics'].get('available', False) else 'FAIL',
        'executions': 'OK' if 'executions' in results and results['executions'].get('available', False) else 'FAIL',
        'workflows': 'OK' if 'workflows' in results and results['workflows'].get('available', False) else 'FAIL',
        'webhooks': 'OK' if 'webhooks' in results and results['webhooks'].get('available', False) else 'FAIL',
        'credentials': 'OK' if 'credentials' in results and results['credentials'].get('available', False) else 'FAIL',
        'users': 'OK' if 'users' in results and results['users'].get('available', False) else 'FAIL',
        'tags': 'OK' if 'tags' in results and results['tags'].get('available', False) else 'FAIL',
        'variables': 'OK' if 'variables' in results and results['variables'].get('available', False) else 'FAIL',
        'projects': 'OK' if 'projects' in results and results['projects'].get('available', False) else 'FAIL',
        'failed_runs_analysis': 'OK' if 'failed_runs_analysis' in results and results['failed_runs_analysis'].get('available', False) else 'FAIL',
        'workflow_executions_analysis': 'OK' if 'workflow_executions_analysis' in results and results['workflow_executions_analysis'].get('available', False) else 'FAIL'
    }
    
    for api_name, status in api_status.items():
        print(f"{api_name};{status}")
    
    # System Info Section
    if 'system' in results:
        system_data = results['system']
        print("<<<n8n_system>>>")
        platform = system_data.get('platform', 'unknown')
        agent_version = system_data.get('agent_version', 'unknown')
        timestamp = system_data.get('timestamp', 'unknown')
        print(f"{platform};{agent_version};{timestamp}")

async def collect_n8n_data(args):
    """Main function to collect n8n monitoring data - Otimizado para execução paralela"""
    try:
        # Configure logging
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Obter timestamp de ativação (cria se não existir)
        activation_time = get_activation_timestamp()
        if activation_time:
            logger.info(f"Using activation timestamp: {activation_time.isoformat()}")
        
        # Initialize monitor
        verify_ssl = not args.no_ssl_verify
        async with N8nMonitor(args.url, args.timeout, verify_ssl, args.user, args.api_password, args.api_key) as monitor:
            results = {}
            
            # Coletar dados básicos em paralelo (métricas, users, tags, variables, projects)
            # Esses são independentes e podem ser executados simultaneamente
            tasks_to_run = []
            task_names = []
            
            # Collect health check data
            if args.healthz_enabled.lower() == "true":
                tasks_to_run.append(monitor.check_healthz())
                task_names.append('healthz')

            # Collect readiness check data
            if args.readiness_enabled.lower() == "true":
                tasks_to_run.append(monitor.check_readiness())
                task_names.append('readiness')

            # Collect metrics data
            if args.metrics_enabled.lower() == "true":
                tasks_to_run.append(monitor.get_metrics())
                task_names.append('metrics')
            
            # Collect users data
            if args.users_enabled.lower() == "true":
                tasks_to_run.append(monitor.get_users())
                task_names.append('users')
            
            # Collect tags data
            if args.tags_enabled.lower() == "true":
                tasks_to_run.append(monitor.get_tags())
                task_names.append('tags')
            
            # Collect variables data
            if args.variables_enabled.lower() == "true":
                tasks_to_run.append(monitor.get_variables())
                task_names.append('variables')
            
            # Collect projects data
            if args.projects_enabled.lower() == "true":
                tasks_to_run.append(monitor.get_projects())
                task_names.append('projects')
            
            # Executar tarefas independentes em paralelo
            if tasks_to_run:
                logger.info(f"Executing {len(tasks_to_run)} independent API calls in parallel...")
                parallel_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                for name, result in zip(task_names, parallel_results):
                    if isinstance(result, Exception):
                        logger.error(f"Error collecting {name}: {result}")
                        results[name] = {"available": False, "error": str(result)}
                    else:
                        results[name] = result
            
            # Coletar dados de execuções primeiro (será reutilizado)
            executions_cache = None
            executions_available = False
            executions_result: Dict = {}
            if (
                args.workflows_enabled.lower() == "true"
                or args.failed_runs_enabled.lower() == "true"
                or args.workflow_executions_enabled.lower() == "true"
                or args.executions_enabled.lower() == "true"
            ):
                # Buscar execuções uma vez para reutilizar
                logger.info("Collecting executions data for reuse...")
                executions_result = await monitor.get_executions(activation_time)
                executions_available = bool(executions_result.get('available', False))
                if executions_available:
                    executions_cache = executions_result.get('executions', {}).get('data', [])
                    logger.info(f"Cached {len(executions_cache)} executions for reuse")
                # Publicar o resultado para que a secção <<<n8n_executions>>> e o
                # estado do endpoint em <<<n8n_api_status>>> reflitam a recolha.
                if args.executions_enabled.lower() == "true":
                    results['executions'] = executions_result
            
            # Collect workflows data (reutiliza execuções já coletadas)
            if args.workflows_enabled.lower() == "true":
                logger.info("Collecting n8n workflows...")
                results['workflows'] = await monitor.get_workflows(activation_time, executions_cache)
            
            # Both analyses are derived from the executions endpoint.  If that
            # endpoint could not be read there is nothing to derive, and
            # deriving it anyway would report "0 failures / 100% success" for a
            # dead n8n.  Mark them unavailable so the sections are omitted.
            unavailable = {
                "status_code": None,
                "available": False,
                "error": executions_result.get('error', 'executions API unavailable'),
            }

            # Collect failed runs analysis data (reutiliza execuções já coletadas)
            if args.failed_runs_enabled.lower() == "true":
                if executions_available:
                    logger.info("Collecting n8n failed runs analysis...")
                    results['failed_runs_analysis'] = await monitor.get_failed_runs_analysis(activation_time, executions_cache)
                else:
                    logger.error("Skipping failed runs analysis: executions data unavailable")
                    results['failed_runs_analysis'] = {"endpoint": "failed_runs_analysis", **unavailable}

            # Collect workflow executions analysis data (reutiliza execuções já coletadas)
            if args.workflow_executions_enabled.lower() == "true":
                if executions_available:
                    logger.info("Collecting n8n workflow executions analysis...")
                    results['workflow_executions_analysis'] = await monitor.get_workflow_executions_analysis(activation_time, executions_cache)
                else:
                    logger.error("Skipping workflow executions analysis: executions data unavailable")
                    results['workflow_executions_analysis'] = {"endpoint": "workflow_executions_analysis", **unavailable}
            
            # Expose the id -> name map so the executions section can label
            # its rows too (executions are fetched with includeData=false).
            results['workflow_names'] = monitor.workflow_names

            # Add system info
            results['system'] = {
                'platform': platform.system(),
                'python_version': sys.version,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'agent_version': '1.0.0'
            }
            
            # Save timestamp
            with open(TIMESTAMP_FILE, 'w') as f:
                f.write(str(int(time.time())))
            
            # Output results in CheckMK format
            output_checkmk_format(results)
            
            return 0
            
    except Exception as e:
        logger.error(f"Error collecting n8n data: {e}")
        return 1

def main():
    args = parse_args()
    
    # Set up logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run async collection
    try:
        exit_code = asyncio.run(collect_n8n_data(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

