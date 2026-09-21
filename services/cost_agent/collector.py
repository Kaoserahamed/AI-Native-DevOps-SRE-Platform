"""Cost evidence collection from multiple sources.

Collects resource utilization, idle resources, LLM usage, storage metrics, and CI usage
to build a comprehensive cost evidence bundle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from packages.contracts.common import ServiceRef
from packages.contracts.cost import (
    CIUsageMetrics,
    CostEvidence,
    IdleResource,
    LLMUsageMetrics,
    ResourceType,
    ResourceUtilization,
    StorageMetrics,
)

logger = logging.getLogger(__name__)


class CostCollector:
    """Collects cost optimization evidence from observability and infrastructure sources."""

    def __init__(
        self,
        prometheus_client: Any = None,
        kubernetes_client: Any = None,
        github_client: Any = None,
    ) -> None:
        """Initialize cost collector with infrastructure clients.

        Parameters
        ----------
        prometheus_client
            Client for querying Prometheus metrics
        kubernetes_client
            Client for querying Kubernetes resources
        github_client
            Client for querying GitHub CI/CD usage
        """
        self.prometheus_client = prometheus_client
        self.kubernetes_client = kubernetes_client
        self.github_client = github_client

    async def collect_resource_utilization(
        self, service: ServiceRef, measurement_window: timedelta
    ) -> list[ResourceUtilization]:
        """Collect CPU and memory utilization for a service.

        Parameters
        ----------
        service
            Service to analyze
        measurement_window
            Time window to measure (e.g., 24 hours)

        Returns
        -------
        list[ResourceUtilization]
            Resource utilization metrics
        """
        logger.info(
            "Collecting resource utilization for %s over %s", service.name, measurement_window
        )

        # In production, query Prometheus for actual metrics
        # Example queries:
        # - CPU: rate(container_cpu_usage_seconds_total[5m])
        # - Memory: container_memory_working_set_bytes
        # - Requested: kube_pod_container_resource_requests

        utilization_metrics = []

        # CPU utilization (stub)
        cpu_utilization = ResourceUtilization(
            service=service,
            resource_type=ResourceType.CPU,
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            requested=2.0,  # 2 cores requested
            actual_used=0.5,  # 0.5 cores actually used
            unit="cores",
            utilization_percent=25.0,
            replica_count=3,
        )
        utilization_metrics.append(cpu_utilization)

        # Memory utilization (stub)
        memory_utilization = ResourceUtilization(
            service=service,
            resource_type=ResourceType.MEMORY,
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            requested=4_294_967_296,  # 4 GiB requested
            actual_used=1_073_741_824,  # 1 GiB actually used
            unit="bytes",
            utilization_percent=25.0,
            replica_count=3,
        )
        utilization_metrics.append(memory_utilization)

        return utilization_metrics

    async def detect_idle_resources(self, service: ServiceRef | None = None) -> list[IdleResource]:
        """Detect idle or underutilized resources.

        Parameters
        ----------
        service
            Optional service to scope detection, or None for all services

        Returns
        -------
        list[IdleResource]
            Identified idle resources
        """
        logger.info("Detecting idle resources for service: %s", service.name if service else "all")

        # In production, query Kubernetes for:
        # - Pods with low CPU/memory usage
        # - PersistentVolumes with no activity
        # - Services with no traffic

        idle_resources = []

        # Example: Idle PersistentVolume (stub)
        if service:
            idle_pv = IdleResource(
                resource_name=f"{service.name}-unused-pv",
                resource_type=ResourceType.STORAGE,
                service=service,
                idle_duration=timedelta(days=30),
                last_activity=datetime.now(tz=UTC) - timedelta(days=30),
                estimated_cost_per_day=0.50,  # $0.50/day
                utilization_percent=0.0,
            )
            idle_resources.append(idle_pv)

        return idle_resources

    async def collect_llm_usage(
        self, service: ServiceRef, measurement_window: timedelta
    ) -> LLMUsageMetrics:
        """Collect LLM token usage and cost metrics.

        Parameters
        ----------
        service
            Service using LLM APIs
        measurement_window
            Time window to measure

        Returns
        -------
        LLMUsageMetrics
            LLM usage metrics
        """
        logger.info("Collecting LLM usage for %s over %s", service.name, measurement_window)

        # In production, query application metrics or LLM provider APIs
        # Track: prompt tokens, completion tokens, requests, model used

        # Stub example
        total_prompt = 150_000
        total_completion = 50_000
        total_requests = 100

        # Example pricing: $0.03/1K prompt tokens, $0.06/1K completion tokens (GPT-4 Turbo)
        estimated_cost = (total_prompt / 1000 * 0.03) + (total_completion / 1000 * 0.06)

        return LLMUsageMetrics(
            service=service,
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_requests=total_requests,
            estimated_cost=estimated_cost,
            model_name="gpt-4-turbo",
            average_tokens_per_request=(total_prompt + total_completion) / total_requests,
        )

    async def collect_storage_metrics(
        self, service: ServiceRef, measurement_window: timedelta
    ) -> list[StorageMetrics]:
        """Collect storage usage and growth metrics.

        Parameters
        ----------
        service
            Service to analyze
        measurement_window
            Time window to measure growth rate

        Returns
        -------
        list[StorageMetrics]
            Storage metrics by type
        """
        logger.info("Collecting storage metrics for %s over %s", service.name, measurement_window)

        # In production, query:
        # - Kubernetes PV usage
        # - Container registry size
        # - Log aggregation storage
        # - Database storage

        storage_metrics = []

        # PersistentVolume usage (stub)
        pv_metrics = StorageMetrics(
            service=service,
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            total_bytes=10_737_418_240,  # 10 GiB
            growth_rate_bytes_per_day=107_374_182,  # ~100 MiB/day
            object_count=1,
            estimated_cost_per_month=2.00,  # $2/month for 10 GiB
            storage_type="pv",
        )
        storage_metrics.append(pv_metrics)

        # Log storage (stub)
        log_metrics = StorageMetrics(
            service=service,
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            total_bytes=53_687_091_200,  # 50 GiB
            growth_rate_bytes_per_day=536_870_912,  # 500 MiB/day
            object_count=1_000_000,
            estimated_cost_per_month=10.00,  # $10/month for 50 GiB
            storage_type="logs",
        )
        storage_metrics.append(log_metrics)

        return storage_metrics

    async def collect_ci_usage(self, measurement_window: timedelta) -> CIUsageMetrics:
        """Collect CI/CD pipeline resource usage.

        Parameters
        ----------
        measurement_window
            Time window to measure

        Returns
        -------
        CIUsageMetrics
            CI usage metrics
        """
        logger.info("Collecting CI usage over %s", measurement_window)

        # In production, query GitHub Actions API or other CI provider
        # Track: total minutes, runs, workflow breakdown

        # Stub example
        workflow_breakdown = {
            "ci.yml": 1200,  # 1200 minutes
            "infrastructure.yml": 300,
            "security.yml": 150,
        }

        total_minutes = sum(workflow_breakdown.values())
        total_runs = 50

        # GitHub Actions pricing: $0.008/minute for Linux
        estimated_cost = total_minutes * 0.008

        return CIUsageMetrics(
            measurement_window=measurement_window,
            measured_at=datetime.now(tz=UTC),
            total_minutes=total_minutes,
            total_runs=total_runs,
            average_duration_minutes=total_minutes / total_runs,
            estimated_cost=estimated_cost,
            workflow_breakdown=workflow_breakdown,
        )

    async def collect_cost_evidence(
        self,
        services: list[ServiceRef],
        measurement_window: timedelta = timedelta(days=7),
    ) -> CostEvidence:
        """Collect comprehensive cost evidence for services.

        Parameters
        ----------
        services
            Services to analyze
        measurement_window
            Time window for analysis

        Returns
        -------
        CostEvidence
            Complete cost evidence bundle
        """
        logger.info("Collecting cost evidence for %d services", len(services))

        all_resource_utilization = []
        all_idle_resources = []
        all_llm_usage = []
        all_storage_metrics = []

        for service in services:
            # Collect resource utilization
            utilization = await self.collect_resource_utilization(service, measurement_window)
            all_resource_utilization.extend(utilization)

            # Detect idle resources
            idle = await self.detect_idle_resources(service)
            all_idle_resources.extend(idle)

            # Collect LLM usage if applicable
            if service.name in ["incident-agent", "remediation-agent", "cost-agent"]:
                llm_usage = await self.collect_llm_usage(service, measurement_window)
                all_llm_usage.append(llm_usage)

            # Collect storage metrics
            storage = await self.collect_storage_metrics(service, measurement_window)
            all_storage_metrics.extend(storage)

        # Collect CI usage (organization-wide)
        ci_usage = await self.collect_ci_usage(measurement_window)

        # Calculate total estimated monthly cost
        total_cost = 0.0
        total_cost += sum(idle.estimated_cost_per_day * 30 for idle in all_idle_resources)
        total_cost += sum(
            llm.estimated_cost * 30 / measurement_window.days for llm in all_llm_usage
        )
        total_cost += sum(storage.estimated_cost_per_month for storage in all_storage_metrics)
        total_cost += ci_usage.estimated_cost * 30 / measurement_window.days

        evidence_id = f"cost-evidence-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"

        return CostEvidence(
            evidence_id=evidence_id,
            collected_at=datetime.now(tz=UTC),
            service=None,  # Organization-wide
            resource_utilization=all_resource_utilization,
            idle_resources=all_idle_resources,
            llm_usage=all_llm_usage,
            storage_metrics=all_storage_metrics,
            ci_usage=ci_usage,
            total_estimated_monthly_cost=total_cost,
        )
