"""Tests for cost recommendation engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.common import Environment, ServiceRef
from packages.contracts.cost import (
    CIUsageMetrics,
    CostCategory,
    CostEvidence,
    CostOptimizationReport,
    IdleResource,
    LLMUsageMetrics,
    ResourceType,
    ResourceUtilization,
    StorageMetrics,
)
from services.cost_agent.recommender import CostRecommender


@pytest.fixture
def cost_recommender() -> CostRecommender:
    """Create a cost recommender instance."""
    return CostRecommender(min_confidence=0.6, min_monthly_savings=10.0)


@pytest.fixture
def test_service() -> ServiceRef:
    """Create a test service reference."""
    return ServiceRef(
        name="demo-api",
        environment=Environment.PRODUCTION,
        namespace="default",
    )


@pytest.fixture
def overprovisioned_cpu(test_service: ServiceRef) -> ResourceUtilization:
    """Create overprovisioned CPU utilization."""
    return ResourceUtilization(
        service=test_service,
        resource_type=ResourceType.CPU,
        measurement_window=timedelta(days=7),
        measured_at=datetime.now(tz=UTC),
        requested=4.0,
        actual_used=1.0,
        unit="cores",
        utilization_percent=25.0,
        replica_count=3,
    )


@pytest.fixture
def overprovisioned_memory(test_service: ServiceRef) -> ResourceUtilization:
    """Create overprovisioned memory utilization."""
    return ResourceUtilization(
        service=test_service,
        resource_type=ResourceType.MEMORY,
        measurement_window=timedelta(days=7),
        measured_at=datetime.now(tz=UTC),
        requested=8_589_934_592,  # 8 GiB
        actual_used=2_147_483_648,  # 2 GiB
        unit="bytes",
        utilization_percent=25.0,
        replica_count=3,
    )


@pytest.fixture
def healthy_utilization(test_service: ServiceRef) -> ResourceUtilization:
    """Create healthy utilization (should not trigger recommendation)."""
    return ResourceUtilization(
        service=test_service,
        resource_type=ResourceType.CPU,
        measurement_window=timedelta(days=7),
        measured_at=datetime.now(tz=UTC),
        requested=2.0,
        actual_used=1.4,
        unit="cores",
        utilization_percent=70.0,
        replica_count=2,
    )


@pytest.fixture
def idle_storage(test_service: ServiceRef) -> IdleResource:
    """Create idle storage resource."""
    return IdleResource(
        resource_name="unused-pv",
        resource_type=ResourceType.STORAGE,
        service=test_service,
        idle_duration=timedelta(days=30),
        last_activity=datetime.now(tz=UTC) - timedelta(days=30),
        estimated_cost_per_day=0.50,
        utilization_percent=0.0,
    )


@pytest.fixture
def high_llm_usage(test_service: ServiceRef) -> LLMUsageMetrics:
    """Create high LLM usage metrics."""
    return LLMUsageMetrics(
        service=test_service,
        measurement_window=timedelta(days=7),
        measured_at=datetime.now(tz=UTC),
        total_prompt_tokens=1_500_000,
        total_completion_tokens=500_000,
        total_requests=100,
        estimated_cost=75.0,
        model_name="gpt-4-turbo",
        average_tokens_per_request=20_000.0,
    )


@pytest.fixture
def log_storage(test_service: ServiceRef) -> StorageMetrics:
    """Create log storage metrics."""
    return StorageMetrics(
        service=test_service,
        measurement_window=timedelta(days=7),
        measured_at=datetime.now(tz=UTC),
        total_bytes=53_687_091_200,  # 50 GiB
        growth_rate_bytes_per_day=536_870_912,  # 500 MiB/day
        object_count=1_000_000,
        estimated_cost_per_month=50.0,
        storage_type="logs",
    )


class TestRightsizingRecommendations:
    """Test suite for rightsizing recommendations."""

    def test_generate_cpu_rightsizing(
        self, cost_recommender: CostRecommender, overprovisioned_cpu: ResourceUtilization
    ) -> None:
        """Test generating CPU rightsizing recommendation."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [overprovisioned_cpu]
        )

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.RIGHTSIZING
        assert "CPU" in rec.title or "cpu" in rec.title
        assert rec.service == overprovisioned_cpu.service
        assert rec.estimated_impact.monthly_savings_usd > 0
        assert len(rec.assumptions) > 0
        assert len(rec.implementation_steps) > 0
        assert len(rec.validation_criteria) > 0
        assert rec.confidence >= cost_recommender.min_confidence

        # Check current and proposed state. The proposal state is a JSON mapping, so the numbers are
        # compared as floats rather than relying on the declared union of scalar values.
        assert rec.current_state["requested"] == overprovisioned_cpu.requested
        assert float(rec.proposed_state["requested"]) < overprovisioned_cpu.requested

    def test_generate_memory_rightsizing(
        self, cost_recommender: CostRecommender, overprovisioned_memory: ResourceUtilization
    ) -> None:
        """Test generating memory rightsizing recommendation."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [overprovisioned_memory]
        )

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.RIGHTSIZING
        assert "memory" in rec.title.lower()
        assert rec.estimated_impact.monthly_savings_usd > 0

    def test_skip_healthy_utilization(
        self, cost_recommender: CostRecommender, healthy_utilization: ResourceUtilization
    ) -> None:
        """Test that healthy utilization does not trigger recommendation."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [healthy_utilization]
        )

        assert len(recommendations) == 0


class TestIdleCleanupRecommendations:
    """Test suite for idle resource cleanup recommendations."""

    def test_generate_idle_cleanup(
        self, cost_recommender: CostRecommender, idle_storage: IdleResource
    ) -> None:
        """Test generating idle cleanup recommendation."""
        recommendations = cost_recommender.generate_idle_cleanup_recommendations([idle_storage])

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.IDLE_CLEANUP
        assert idle_storage.resource_name in rec.title
        assert rec.estimated_impact.monthly_savings_usd > 0
        assert len(rec.assumptions) > 0
        assert len(rec.implementation_steps) > 0
        assert (
            "delete" in str(rec.proposed_state.get("action", "")).lower()
            or "archive" in rec.description.lower()
        )

    def test_skip_low_cost_idle_resources(self, cost_recommender: CostRecommender) -> None:
        """Test that low-cost idle resources are skipped."""
        cheap_idle = IdleResource(
            resource_name="cheap-resource",
            resource_type=ResourceType.STORAGE,
            idle_duration=timedelta(days=10),
            last_activity=datetime.now(tz=UTC) - timedelta(days=10),
            estimated_cost_per_day=0.01,  # $0.30/month - below threshold
            utilization_percent=0.0,
        )

        recommendations = cost_recommender.generate_idle_cleanup_recommendations([cheap_idle])

        assert len(recommendations) == 0


class TestLLMOptimizationRecommendations:
    """Test suite for LLM optimization recommendations."""

    def test_generate_llm_optimization(
        self, cost_recommender: CostRecommender, high_llm_usage: LLMUsageMetrics
    ) -> None:
        """Test generating LLM optimization recommendation."""
        recommendations = cost_recommender.generate_llm_optimization_recommendations(
            [high_llm_usage]
        )

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.MODEL_SELECTION
        assert "LLM" in rec.title or "token" in rec.title.lower()
        assert rec.service == high_llm_usage.service
        assert rec.estimated_impact.monthly_savings_usd > 0
        assert len(rec.assumptions) > 0
        assert "caching" in rec.description.lower() or "context" in rec.description.lower()

    def test_skip_low_token_usage(
        self, cost_recommender: CostRecommender, test_service: ServiceRef
    ) -> None:
        """Test that low token usage does not trigger recommendation."""
        low_usage = LLMUsageMetrics(
            service=test_service,
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_prompt_tokens=50_000,
            total_completion_tokens=10_000,
            total_requests=100,
            estimated_cost=2.0,
            model_name="gpt-4-turbo",
            average_tokens_per_request=600.0,  # Below 10K threshold
        )

        recommendations = cost_recommender.generate_llm_optimization_recommendations([low_usage])

        assert len(recommendations) == 0


class TestLogRetentionRecommendations:
    """Test suite for log retention recommendations."""

    def test_generate_log_retention(
        self, cost_recommender: CostRecommender, log_storage: StorageMetrics
    ) -> None:
        """Test generating log retention recommendation."""
        recommendations = cost_recommender.generate_log_retention_recommendations([log_storage])

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.LOG_RETENTION
        assert "log" in rec.title.lower()
        assert rec.service == log_storage.service
        assert rec.estimated_impact.monthly_savings_usd > 0
        assert "retention" in rec.description.lower()
        assert len(rec.implementation_steps) > 0

    def test_skip_non_log_storage(
        self, cost_recommender: CostRecommender, test_service: ServiceRef
    ) -> None:
        """Test that non-log storage is skipped."""
        pv_storage = StorageMetrics(
            service=test_service,
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_bytes=10_737_418_240,
            growth_rate_bytes_per_day=1_073_741,
            object_count=1,
            estimated_cost_per_month=10.0,
            storage_type="pv",  # Not logs
        )

        recommendations = cost_recommender.generate_log_retention_recommendations([pv_storage])

        assert len(recommendations) == 0


class TestAutoscalingRecommendations:
    """Test suite for autoscaling recommendations."""

    def test_generate_autoscaling(
        self,
        cost_recommender: CostRecommender,
        overprovisioned_cpu: ResourceUtilization,
        overprovisioned_memory: ResourceUtilization,
    ) -> None:
        """Test generating autoscaling recommendation."""
        # Both utilizations have low usage and multiple replicas
        recommendations = cost_recommender.generate_autoscaling_recommendations(
            [overprovisioned_cpu, overprovisioned_memory]
        )

        assert len(recommendations) > 0
        rec = recommendations[0]

        assert rec.category == CostCategory.AUTOSCALING
        assert "autoscal" in rec.title.lower()
        assert rec.estimated_impact.monthly_savings_usd > 0
        assert "HPA" in rec.description or "HorizontalPodAutoscaler" in "\n".join(
            rec.implementation_steps
        )

        # Check proposed state has autoscaling config
        assert "minReplicas" in rec.proposed_state
        assert "maxReplicas" in rec.proposed_state


class TestCostOptimizationReport:
    """Test suite for complete cost optimization report generation."""

    @pytest.fixture
    def sample_evidence(
        self,
        test_service: ServiceRef,
        overprovisioned_cpu: ResourceUtilization,
        idle_storage: IdleResource,
        high_llm_usage: LLMUsageMetrics,
        log_storage: StorageMetrics,
    ) -> CostEvidence:
        """Create sample cost evidence."""
        ci_usage = CIUsageMetrics(
            measurement_window=timedelta(days=7),
            measured_at=datetime.now(tz=UTC),
            total_minutes=1650,
            total_runs=50,
            average_duration_minutes=33.0,
            estimated_cost=13.20,
            workflow_breakdown={},
        )

        return CostEvidence(
            evidence_id="test-evidence-001",
            collected_at=datetime.now(tz=UTC),
            service=test_service,
            resource_utilization=[overprovisioned_cpu],
            idle_resources=[idle_storage],
            llm_usage=[high_llm_usage],
            storage_metrics=[log_storage],
            ci_usage=ci_usage,
            total_estimated_monthly_cost=500.0,
        )

    @pytest.mark.asyncio
    async def test_generate_full_report(
        self, cost_recommender: CostRecommender, sample_evidence: CostEvidence
    ) -> None:
        """Test generating complete cost optimization report."""
        report = await cost_recommender.generate_recommendations(evidence=sample_evidence)

        assert isinstance(report, CostOptimizationReport)
        assert report.report_id
        assert report.generated_at
        assert report.evidence_summary == sample_evidence
        assert len(report.recommendations) > 0
        assert report.total_potential_monthly_savings > 0
        assert report.total_current_monthly_cost == sample_evidence.total_estimated_monthly_cost
        assert len(report.analyzed_services) > 0

    @pytest.mark.asyncio
    async def test_report_filters_by_confidence(self, sample_evidence: CostEvidence) -> None:
        """Test that report filters recommendations by confidence threshold."""
        # Use high confidence threshold
        recommender = CostRecommender(min_confidence=0.9, min_monthly_savings=1.0)

        report = await recommender.generate_recommendations(evidence=sample_evidence)

        # With high threshold, fewer recommendations should pass
        for rec in report.recommendations:
            assert rec.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_report_calculates_total_savings(
        self, cost_recommender: CostRecommender, sample_evidence: CostEvidence
    ) -> None:
        """Test that report correctly calculates total potential savings."""
        report = await cost_recommender.generate_recommendations(evidence=sample_evidence)

        calculated_total = sum(
            rec.estimated_impact.monthly_savings_usd for rec in report.recommendations
        )

        assert report.total_potential_monthly_savings == calculated_total

    @pytest.mark.asyncio
    async def test_report_includes_all_categories(
        self, cost_recommender: CostRecommender, sample_evidence: CostEvidence
    ) -> None:
        """Test that report can include recommendations from all categories."""
        report = await cost_recommender.generate_recommendations(evidence=sample_evidence)

        categories = {rec.category for rec in report.recommendations}

        # Should have multiple categories represented
        assert len(categories) >= 2


class TestRecommendationQuality:
    """Test suite for recommendation quality and completeness."""

    def test_recommendations_have_assumptions(
        self, cost_recommender: CostRecommender, overprovisioned_cpu: ResourceUtilization
    ) -> None:
        """Test that all recommendations include assumptions."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [overprovisioned_cpu]
        )

        for rec in recommendations:
            assert len(rec.assumptions) > 0
            for assumption in rec.assumptions:
                assert assumption.description
                assert 0 <= assumption.confidence <= 1
                assert assumption.source

    def test_recommendations_have_impact_estimates(
        self, cost_recommender: CostRecommender, overprovisioned_cpu: ResourceUtilization
    ) -> None:
        """Test that all recommendations include impact estimates."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [overprovisioned_cpu]
        )

        for rec in recommendations:
            impact = rec.estimated_impact
            assert impact.monthly_savings_usd > 0
            assert 0 <= impact.percentage_reduction <= 100
            assert len(impact.affected_services) > 0
            assert impact.implementation_effort in ["low", "medium", "high"]
            assert impact.risk_level in ["low", "medium", "high"]

    def test_recommendations_have_implementation_steps(
        self, cost_recommender: CostRecommender, idle_storage: IdleResource
    ) -> None:
        """Test that all recommendations include implementation steps."""
        recommendations = cost_recommender.generate_idle_cleanup_recommendations([idle_storage])

        for rec in recommendations:
            assert len(rec.implementation_steps) > 0
            assert all(step for step in rec.implementation_steps)  # No empty steps

    def test_recommendations_have_validation_criteria(
        self, cost_recommender: CostRecommender, log_storage: StorageMetrics
    ) -> None:
        """Test that all recommendations include validation criteria."""
        recommendations = cost_recommender.generate_log_retention_recommendations([log_storage])

        for rec in recommendations:
            assert len(rec.validation_criteria) > 0
            assert all(criterion for criterion in rec.validation_criteria)

    def test_recommendations_have_current_and_proposed_state(
        self, cost_recommender: CostRecommender, overprovisioned_cpu: ResourceUtilization
    ) -> None:
        """Test that recommendations include current and proposed states."""
        recommendations = cost_recommender.generate_rightsizing_recommendations(
            [overprovisioned_cpu]
        )

        for rec in recommendations:
            assert rec.current_state
            assert rec.proposed_state
            # Proposed should differ from current
            assert rec.current_state != rec.proposed_state
