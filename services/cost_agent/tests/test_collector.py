"""Tests for cost evidence collector."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.common import Environment, ServiceRef
from packages.contracts.cost import (
    CIUsageMetrics,
    CostEvidence,
    IdleResource,
    LLMUsageMetrics,
    ResourceType,
    ResourceUtilization,
    StorageMetrics,
)
from services.cost_agent.collector import CostCollector


@pytest.fixture
def cost_collector() -> CostCollector:
    """Create a cost collector instance."""
    return CostCollector()


@pytest.fixture
def test_service() -> ServiceRef:
    """Create a test service reference."""
    return ServiceRef(
        name="demo-api",
        environment=Environment.PRODUCTION,
        namespace="default",
    )


class TestCostCollector:
    """Test suite for CostCollector."""

    @pytest.mark.asyncio
    async def test_collect_resource_utilization(
        self, cost_collector: CostCollector, test_service: ServiceRef
    ) -> None:
        """Test collecting resource utilization metrics."""
        measurement_window = timedelta(hours=24)

        utilization = await cost_collector.collect_resource_utilization(
            service=test_service, measurement_window=measurement_window
        )

        assert isinstance(utilization, list)
        assert len(utilization) > 0

        # Check CPU metrics
        cpu_metrics = [u for u in utilization if u.resource_type == ResourceType.CPU]
        assert len(cpu_metrics) > 0
        cpu = cpu_metrics[0]
        assert cpu.service == test_service
        assert cpu.requested > 0
        assert cpu.actual_used >= 0
        assert 0 <= cpu.utilization_percent <= 100
        assert cpu.unit == "cores"

        # Check memory metrics
        mem_metrics = [u for u in utilization if u.resource_type == ResourceType.MEMORY]
        assert len(mem_metrics) > 0
        mem = mem_metrics[0]
        assert mem.service == test_service
        assert mem.unit == "bytes"

    @pytest.mark.asyncio
    async def test_detect_idle_resources(
        self, cost_collector: CostCollector, test_service: ServiceRef
    ) -> None:
        """Test detecting idle resources."""
        idle_resources = await cost_collector.detect_idle_resources(service=test_service)

        assert isinstance(idle_resources, list)

        for idle in idle_resources:
            assert isinstance(idle, IdleResource)
            assert idle.resource_name
            assert idle.idle_duration > timedelta(0)
            assert idle.estimated_cost_per_day >= 0
            assert 0 <= idle.utilization_percent <= 100

    @pytest.mark.asyncio
    async def test_collect_llm_usage(
        self, cost_collector: CostCollector, test_service: ServiceRef
    ) -> None:
        """Test collecting LLM usage metrics."""
        measurement_window = timedelta(days=7)

        llm_usage = await cost_collector.collect_llm_usage(
            service=test_service, measurement_window=measurement_window
        )

        assert isinstance(llm_usage, LLMUsageMetrics)
        assert llm_usage.service == test_service
        assert llm_usage.total_prompt_tokens > 0
        assert llm_usage.total_completion_tokens > 0
        assert llm_usage.total_requests > 0
        assert llm_usage.estimated_cost >= 0
        assert llm_usage.model_name
        assert llm_usage.average_tokens_per_request > 0

    @pytest.mark.asyncio
    async def test_collect_storage_metrics(
        self, cost_collector: CostCollector, test_service: ServiceRef
    ) -> None:
        """Test collecting storage metrics."""
        measurement_window = timedelta(days=7)

        storage = await cost_collector.collect_storage_metrics(
            service=test_service, measurement_window=measurement_window
        )

        assert isinstance(storage, list)
        assert len(storage) > 0

        for metrics in storage:
            assert isinstance(metrics, StorageMetrics)
            assert metrics.service == test_service
            assert metrics.total_bytes > 0
            assert metrics.estimated_cost_per_month >= 0
            assert metrics.storage_type in ["pv", "logs", "registry"]

    @pytest.mark.asyncio
    async def test_collect_ci_usage(self, cost_collector: CostCollector) -> None:
        """Test collecting CI usage metrics."""
        measurement_window = timedelta(days=7)

        ci_usage = await cost_collector.collect_ci_usage(measurement_window=measurement_window)

        assert isinstance(ci_usage, CIUsageMetrics)
        assert ci_usage.total_minutes > 0
        assert ci_usage.total_runs > 0
        assert ci_usage.average_duration_minutes > 0
        assert ci_usage.estimated_cost >= 0
        assert ci_usage.workflow_breakdown

    @pytest.mark.asyncio
    async def test_collect_cost_evidence(
        self, cost_collector: CostCollector, test_service: ServiceRef
    ) -> None:
        """Test collecting comprehensive cost evidence."""
        services = [test_service]
        measurement_window = timedelta(days=7)

        evidence = await cost_collector.collect_cost_evidence(
            services=services, measurement_window=measurement_window
        )

        assert isinstance(evidence, CostEvidence)
        assert evidence.evidence_id
        assert evidence.collected_at
        assert len(evidence.resource_utilization) > 0
        assert evidence.ci_usage is not None
        assert evidence.total_estimated_monthly_cost >= 0

    @pytest.mark.asyncio
    async def test_collect_evidence_multiple_services(self, cost_collector: CostCollector) -> None:
        """Test collecting evidence for multiple services."""
        services = [
            ServiceRef(name="demo-api", environment=Environment.PRODUCTION),
            ServiceRef(name="incident-agent", environment=Environment.PRODUCTION),
        ]

        evidence = await cost_collector.collect_cost_evidence(services=services)

        assert len(evidence.resource_utilization) >= len(services) * 2  # CPU + memory per service
        assert len(evidence.llm_usage) > 0  # incident-agent uses LLM


class TestResourceUtilization:
    """Test suite for ResourceUtilization model."""

    def test_resource_utilization_creation(self, test_service: ServiceRef) -> None:
        """Test creating resource utilization."""
        util = ResourceUtilization(
            service=test_service,
            resource_type=ResourceType.CPU,
            measurement_window=timedelta(hours=24),
            measured_at=datetime.now(tz=UTC),
            requested=2.0,
            actual_used=0.5,
            unit="cores",
            utilization_percent=25.0,
            replica_count=3,
        )

        assert util.service == test_service
        assert util.resource_type == ResourceType.CPU
        assert util.requested == 2.0
        assert util.actual_used == 0.5
        assert util.utilization_percent == 25.0

    def test_resource_utilization_validates_non_negative(self, test_service: ServiceRef) -> None:
        """Test resource utilization validates non-negative values."""
        with pytest.raises(ValueError, match="requested"):
            ResourceUtilization(
                service=test_service,
                resource_type=ResourceType.MEMORY,
                measurement_window=timedelta(hours=24),
                measured_at=datetime.now(tz=UTC),
                requested=-1.0,  # Invalid
                actual_used=0.5,
                unit="bytes",
                utilization_percent=0,
                replica_count=1,
            )


class TestIdleResource:
    """Test suite for IdleResource model."""

    def test_idle_resource_creation(self, test_service: ServiceRef) -> None:
        """Test creating idle resource."""
        idle = IdleResource(
            resource_name="unused-pv",
            resource_type=ResourceType.STORAGE,
            service=test_service,
            idle_duration=timedelta(days=30),
            last_activity=datetime.now(tz=UTC) - timedelta(days=30),
            estimated_cost_per_day=0.50,
            utilization_percent=0.0,
        )

        assert idle.resource_name == "unused-pv"
        assert idle.resource_type == ResourceType.STORAGE
        assert idle.idle_duration == timedelta(days=30)
        assert idle.estimated_cost_per_day == 0.50


class TestLLMUsageMetrics:
    """Test suite for LLMUsageMetrics model."""

    def test_llm_usage_creation(self, test_service: ServiceRef) -> None:
        """Test creating LLM usage metrics."""
        usage = LLMUsageMetrics(
            service=test_service,
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_prompt_tokens=150_000,
            total_completion_tokens=50_000,
            total_requests=100,
            estimated_cost=7.50,
            model_name="gpt-4-turbo",
            average_tokens_per_request=2000.0,
        )

        assert usage.total_prompt_tokens == 150_000
        assert usage.total_completion_tokens == 50_000
        assert usage.estimated_cost == 7.50
        assert usage.model_name == "gpt-4-turbo"


class TestStorageMetrics:
    """Test suite for StorageMetrics model."""

    def test_storage_metrics_creation(self, test_service: ServiceRef) -> None:
        """Test creating storage metrics."""
        metrics = StorageMetrics(
            service=test_service,
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_bytes=10_737_418_240,
            growth_rate_bytes_per_day=107_374_182,
            object_count=1,
            estimated_cost_per_month=2.00,
            storage_type="pv",
        )

        assert metrics.total_bytes == 10_737_418_240
        assert metrics.growth_rate_bytes_per_day == 107_374_182
        assert metrics.storage_type == "pv"


class TestCIUsageMetrics:
    """Test suite for CIUsageMetrics model."""

    def test_ci_usage_creation(self) -> None:
        """Test creating CI usage metrics."""
        usage = CIUsageMetrics(
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_minutes=1650,
            total_runs=50,
            average_duration_minutes=33.0,
            estimated_cost=13.20,
            workflow_breakdown={"ci.yml": 1200, "infrastructure.yml": 300, "security.yml": 150},
        )

        assert usage.total_minutes == 1650
        assert usage.total_runs == 50
        assert usage.average_duration_minutes == 33.0
        assert usage.estimated_cost == 13.20
        assert len(usage.workflow_breakdown) == 3


class TestCostEvidence:
    """Test suite for CostEvidence model."""

    def test_cost_evidence_creation(self, test_service: ServiceRef) -> None:
        """Test creating cost evidence."""
        evidence = CostEvidence(
            evidence_id="cost-evidence-001",
            collected_at=datetime.now(tz=UTC),
            service=test_service,
            total_estimated_monthly_cost=100.0,
        )

        assert evidence.evidence_id == "cost-evidence-001"
        assert evidence.total_estimated_monthly_cost == 100.0
        assert evidence.service == test_service
