"""Cost optimization recommendation engine.

Analyzes cost evidence and produces actionable, non-mutating recommendations with
assumptions, estimated impact, and implementation guidance.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from packages.contracts.common import Environment, ServiceRef
from packages.contracts.cost import (
    CostAssumption,
    CostCategory,
    CostEvidence,
    CostOptimizationReport,
    CostRecommendation,
    EstimatedImpact,
    IdleResource,
    LLMUsageMetrics,
    ResourceType,
    ResourceUtilization,
    StorageMetrics,
)

logger = logging.getLogger(__name__)


class CostRecommender:
    """Generates cost optimization recommendations from evidence."""

    def __init__(self, min_confidence: float = 0.6, min_monthly_savings: float = 10.0) -> None:
        """Initialize cost recommender.

        Parameters
        ----------
        min_confidence
            Minimum confidence threshold for recommendations (0.0-1.0)
        min_monthly_savings
            Minimum monthly savings in USD to consider recommendation worthwhile
        """
        self.min_confidence = min_confidence
        self.min_monthly_savings = min_monthly_savings

    def generate_rightsizing_recommendations(
        self, utilization: list[ResourceUtilization]
    ) -> list[CostRecommendation]:
        """Generate rightsizing recommendations based on utilization data.

        Parameters
        ----------
        utilization
            Resource utilization metrics

        Returns
        -------
        list[CostRecommendation]
            Rightsizing recommendations
        """
        recommendations = []

        for util in utilization:
            # Skip if utilization is healthy (50-85% range)
            if 50.0 <= util.utilization_percent <= 85.0:
                continue

            # Calculate potential savings
            if util.utilization_percent < 50.0:
                # Overprovisioned - recommend reduction
                reduction_factor = (util.utilization_percent + 20.0) / 100.0  # Target 70% usage
                new_requested = util.requested * reduction_factor
                savings_factor = 1.0 - reduction_factor

                # Estimate cost (very rough heuristics)
                if util.resource_type == ResourceType.CPU:
                    # ~$20/month per CPU core
                    monthly_savings = util.requested * savings_factor * 20.0 * util.replica_count
                elif util.resource_type == ResourceType.MEMORY:
                    # ~$2/month per GiB
                    memory_gb = util.requested / (1024**3)
                    monthly_savings = memory_gb * savings_factor * 2.0 * util.replica_count
                else:
                    monthly_savings = 0.0

                if monthly_savings < self.min_monthly_savings:
                    continue

                recommendation_id = f"rightsizing-{util.service.name}-{util.resource_type}-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"

                recommendations.append(
                    CostRecommendation(
                        recommendation_id=recommendation_id,
                        created_at=datetime.now(tz=UTC),
                        category=CostCategory.RIGHTSIZING,
                        title=f"Rightsize {util.resource_type} for {util.service.name}",
                        description=f"Service {util.service.name} is using only {util.utilization_percent:.1f}% "
                        f"of its requested {util.resource_type} resources. Reducing requests from "
                        f"{util.requested:.2f} to {new_requested:.2f} {util.unit} would maintain "
                        f"headroom while reducing cost.",
                        evidence_ids=[f"util-{util.service.name}-{util.resource_type}"],
                        assumptions=[
                            CostAssumption(
                                description="Usage pattern remains stable over time",
                                confidence=0.7,
                                source="7-day historical measurement",
                            ),
                            CostAssumption(
                                description="Targeting 70% utilization provides adequate headroom",
                                confidence=0.8,
                                source="SRE best practice",
                            ),
                            CostAssumption(
                                description="Cost estimate based on cloud provider pricing",
                                confidence=0.9,
                                source="Public pricing data",
                            ),
                        ],
                        estimated_impact=EstimatedImpact(
                            monthly_savings_usd=monthly_savings,
                            percentage_reduction=savings_factor * 100,
                            affected_services=[util.service],
                            implementation_effort="low",
                            risk_level="low",
                        ),
                        implementation_steps=[
                            f"Update resource requests in {util.service.name} deployment manifest",
                            f"Reduce {util.resource_type} request from {util.requested:.2f} to {new_requested:.2f} {util.unit}",
                            "Deploy to staging environment first",
                            "Monitor for 24-48 hours",
                            "Deploy to production if stable",
                        ],
                        validation_criteria=[
                            "Target utilization reaches 65-75% range",
                            "No service degradation or throttling",
                            "P95 latency remains within SLO",
                            "Cost reduction visible in billing dashboard within 1 week",
                        ],
                        confidence=0.75,
                        service=util.service,
                        current_state={
                            "resource_type": util.resource_type,
                            "requested": util.requested,
                            "utilization_percent": util.utilization_percent,
                            "replicas": util.replica_count,
                        },
                        proposed_state={
                            "resource_type": util.resource_type,
                            "requested": new_requested,
                            "target_utilization_percent": 70.0,
                            "replicas": util.replica_count,
                        },
                    )
                )

        return recommendations

    def generate_idle_cleanup_recommendations(
        self, idle_resources: list[IdleResource]
    ) -> list[CostRecommendation]:
        """Generate recommendations for cleaning up idle resources.

        Parameters
        ----------
        idle_resources
            Identified idle resources

        Returns
        -------
        list[CostRecommendation]
            Cleanup recommendations
        """
        recommendations = []

        for idle in idle_resources:
            monthly_savings = idle.estimated_cost_per_day * 30

            if monthly_savings < self.min_monthly_savings:
                continue

            recommendation_id = (
                f"idle-cleanup-{idle.resource_name}-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"
            )

            recommendations.append(
                CostRecommendation(
                    recommendation_id=recommendation_id,
                    created_at=datetime.now(tz=UTC),
                    category=CostCategory.IDLE_CLEANUP,
                    title=f"Remove idle {idle.resource_type}: {idle.resource_name}",
                    description=f"Resource {idle.resource_name} has been idle for "
                    f"{idle.idle_duration.days} days with {idle.utilization_percent:.1f}% utilization. "
                    f"No activity detected since {idle.last_activity.isoformat()}. "
                    f"Removing this resource could save ${monthly_savings:.2f}/month.",
                    evidence_ids=[f"idle-{idle.resource_name}"],
                    assumptions=[
                        CostAssumption(
                            description="Resource will not be needed in the future",
                            confidence=0.6,
                            source=f"{idle.idle_duration.days}-day observation period",
                        ),
                        CostAssumption(
                            description="No undocumented dependencies exist",
                            confidence=0.7,
                            source="Resource graph analysis",
                        ),
                    ],
                    estimated_impact=EstimatedImpact(
                        monthly_savings_usd=monthly_savings,
                        percentage_reduction=100.0,
                        affected_services=[idle.service] if idle.service else [],
                        implementation_effort="low",
                        risk_level="low",
                    ),
                    implementation_steps=[
                        f"Verify no services reference {idle.resource_name}",
                        "Create snapshot or backup if needed",
                        f"Delete or archive {idle.resource_name}",
                        "Monitor for 48 hours for unexpected failures",
                    ],
                    validation_criteria=[
                        "No service errors or failures",
                        "Cost reduction visible in billing",
                        "Resource successfully deleted",
                    ],
                    confidence=0.65,
                    service=idle.service,
                    current_state={
                        "resource_name": idle.resource_name,
                        "resource_type": idle.resource_type,
                        "idle_days": idle.idle_duration.days,
                        "utilization_percent": idle.utilization_percent,
                    },
                    proposed_state={
                        "resource_name": idle.resource_name,
                        "action": "delete",
                    },
                )
            )

        return recommendations

    def generate_llm_optimization_recommendations(
        self, llm_usage: list[LLMUsageMetrics]
    ) -> list[CostRecommendation]:
        """Generate LLM cost optimization recommendations.

        Parameters
        ----------
        llm_usage
            LLM usage metrics

        Returns
        -------
        list[CostRecommendation]
            LLM optimization recommendations
        """
        recommendations = []

        for usage in llm_usage:
            avg_tokens = usage.average_tokens_per_request

            # If average request uses > 10K tokens, consider optimization
            if avg_tokens > 10_000:
                # Estimate savings from reducing context or using cheaper model
                # Assume 30% reduction in tokens is possible
                potential_savings_factor = 0.30
                monthly_cost = usage.estimated_cost * 30 / usage.measurement_window.days
                monthly_savings = monthly_cost * potential_savings_factor

                if monthly_savings < self.min_monthly_savings:
                    continue

                recommendation_id = f"llm-optimization-{usage.service.name}-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"

                recommendations.append(
                    CostRecommendation(
                        recommendation_id=recommendation_id,
                        created_at=datetime.now(tz=UTC),
                        category=CostCategory.MODEL_SELECTION,
                        title=f"Optimize LLM context size for {usage.service.name}",
                        description=f"Service {usage.service.name} is using {avg_tokens:.0f} tokens per request "
                        f"on average with {usage.model_name}. Reducing prompt context, implementing "
                        f"better caching, or using a more efficient model could reduce costs.",
                        evidence_ids=[f"llm-usage-{usage.service.name}"],
                        assumptions=[
                            CostAssumption(
                                description="30% token reduction is achievable through optimization",
                                confidence=0.7,
                                source="Industry benchmarks",
                            ),
                            CostAssumption(
                                description="Quality remains acceptable with reduced context",
                                confidence=0.6,
                                source="A/B testing assumption",
                            ),
                        ],
                        estimated_impact=EstimatedImpact(
                            monthly_savings_usd=monthly_savings,
                            percentage_reduction=potential_savings_factor * 100,
                            affected_services=[usage.service],
                            implementation_effort="medium",
                            risk_level="medium",
                        ),
                        implementation_steps=[
                            "Analyze typical prompts for redundancy",
                            "Implement prompt caching for repeated queries",
                            "Remove unnecessary context from prompts",
                            "Consider using a smaller model for simpler tasks",
                            "A/B test to verify quality is maintained",
                        ],
                        validation_criteria=[
                            "Average tokens per request reduced by ≥20%",
                            "Agent output quality scores remain ≥90%",
                            "Cost reduction visible in LLM provider billing",
                        ],
                        confidence=0.65,
                        service=usage.service,
                        current_state={
                            "model": usage.model_name,
                            "avg_tokens_per_request": avg_tokens,
                            "total_requests": usage.total_requests,
                            "estimated_monthly_cost": monthly_cost,
                        },
                        proposed_state={
                            "model": usage.model_name,
                            "target_avg_tokens_per_request": avg_tokens * 0.7,
                            "optimization": "context reduction + caching",
                        },
                    )
                )

        return recommendations

    def generate_log_retention_recommendations(
        self, storage: list[StorageMetrics]
    ) -> list[CostRecommendation]:
        """Generate log retention optimization recommendations.

        Parameters
        ----------
        storage
            Storage metrics including log storage

        Returns
        -------
        list[CostRecommendation]
            Log retention recommendations
        """
        recommendations = []

        for metrics in storage:
            if metrics.storage_type != "logs":
                continue

            # If logs are growing rapidly and costing significantly
            if metrics.growth_rate_bytes_per_day > 100_000_000:  # > 100 MiB/day
                # Estimate savings from reducing retention
                # Assume reducing retention from 90 to 30 days saves 67%
                savings_factor = 0.67
                monthly_savings = metrics.estimated_cost_per_month * savings_factor

                if monthly_savings < self.min_monthly_savings:
                    continue

                recommendation_id = f"log-retention-{metrics.service.name}-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"

                recommendations.append(
                    CostRecommendation(
                        recommendation_id=recommendation_id,
                        created_at=datetime.now(tz=UTC),
                        category=CostCategory.LOG_RETENTION,
                        title=f"Adjust log retention for {metrics.service.name}",
                        description=f"Service {metrics.service.name} log storage is growing at "
                        f"{metrics.growth_rate_bytes_per_day / (1024**3):.2f} GiB/day. "
                        f"Current storage: {metrics.total_bytes / (1024**3):.1f} GiB. "
                        f"Reducing retention or implementing tiered storage could reduce costs.",
                        evidence_ids=[f"storage-logs-{metrics.service.name}"],
                        assumptions=[
                            CostAssumption(
                                description="Logs older than 30 days rarely accessed",
                                confidence=0.8,
                                source="Access pattern analysis",
                            ),
                            CostAssumption(
                                description="Compliance requirements met with 30-day hot retention",
                                confidence=0.7,
                                source="Policy review assumption",
                            ),
                        ],
                        estimated_impact=EstimatedImpact(
                            monthly_savings_usd=monthly_savings,
                            percentage_reduction=savings_factor * 100,
                            affected_services=[metrics.service],
                            implementation_effort="low",
                            risk_level="low",
                        ),
                        implementation_steps=[
                            "Verify compliance and audit requirements",
                            "Configure log retention to 30 days hot, 90 days archive",
                            "Implement lifecycle policies for automatic archival",
                            "Archive existing logs older than 30 days to cold storage",
                            "Monitor for any access to archived logs",
                        ],
                        validation_criteria=[
                            "Hot storage size stabilizes at ~30 days worth",
                            "Cost reduction visible within 1 week",
                            "No compliance violations",
                            "Archive retrieval process tested and functional",
                        ],
                        confidence=0.75,
                        service=metrics.service,
                        current_state={
                            "total_bytes": metrics.total_bytes,
                            "growth_rate_bytes_per_day": metrics.growth_rate_bytes_per_day,
                            "estimated_retention_days": 90,
                        },
                        proposed_state={
                            "hot_retention_days": 30,
                            "archive_retention_days": 90,
                            "storage_tier": "hot + cold",
                        },
                    )
                )

        return recommendations

    def generate_autoscaling_recommendations(
        self, utilization: list[ResourceUtilization]
    ) -> list[CostRecommendation]:
        """Generate autoscaling recommendations.

        Parameters
        ----------
        utilization
            Resource utilization metrics

        Returns
        -------
        list[CostRecommendation]
            Autoscaling recommendations
        """
        recommendations = []

        # Group utilization by service
        service_utils: dict[str, list[ResourceUtilization]] = {}
        for util in utilization:
            key = f"{util.service.name}-{util.service.environment}"
            if key not in service_utils:
                service_utils[key] = []
            service_utils[key].append(util)

        for utils in service_utils.values():
            # If service has low utilization and fixed replicas
            avg_utilization = sum(u.utilization_percent for u in utils) / len(utils)

            if avg_utilization < 40.0 and utils[0].replica_count > 1:
                # Recommend autoscaling to reduce base replica count
                current_replicas = utils[0].replica_count
                min_replicas = max(1, current_replicas // 2)

                # Estimate savings: 50% reduction in base replicas
                monthly_savings = 0.0
                for util in utils:
                    if util.resource_type == ResourceType.CPU:
                        monthly_savings += util.requested * 0.5 * 20.0 * current_replicas
                    elif util.resource_type == ResourceType.MEMORY:
                        memory_gb = util.requested / (1024**3)
                        monthly_savings += memory_gb * 0.5 * 2.0 * current_replicas

                if monthly_savings < self.min_monthly_savings:
                    continue

                recommendation_id = f"autoscaling-{utils[0].service.name}-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"

                recommendations.append(
                    CostRecommendation(
                        recommendation_id=recommendation_id,
                        created_at=datetime.now(tz=UTC),
                        category=CostCategory.AUTOSCALING,
                        title=f"Enable autoscaling for {utils[0].service.name}",
                        description=f"Service {utils[0].service.name} runs {current_replicas} replicas "
                        f"with {avg_utilization:.1f}% average utilization. Implementing HPA could "
                        f"reduce baseline replicas to {min_replicas} while maintaining capacity during peaks.",
                        evidence_ids=[f"util-{utils[0].service.name}"],
                        assumptions=[
                            CostAssumption(
                                description="Traffic patterns have predictable peaks and valleys",
                                confidence=0.7,
                                source="Historical utilization pattern",
                            ),
                            CostAssumption(
                                description="Service can scale horizontally without data consistency issues",
                                confidence=0.8,
                                source="Architecture review",
                            ),
                        ],
                        estimated_impact=EstimatedImpact(
                            monthly_savings_usd=monthly_savings,
                            percentage_reduction=50.0,
                            affected_services=[utils[0].service],
                            implementation_effort="medium",
                            risk_level="medium",
                        ),
                        implementation_steps=[
                            f"Configure HorizontalPodAutoscaler for {utils[0].service.name}",
                            f"Set minReplicas={min_replicas}, maxReplicas={current_replicas + 2}",
                            "Set target CPU utilization to 70%",
                            "Deploy to staging and test scaling behavior",
                            "Monitor scaling events and adjust thresholds",
                            "Deploy to production",
                        ],
                        validation_criteria=[
                            f"Replicas scale between {min_replicas} and {current_replicas + 2}",
                            "Service maintains SLO during scale events",
                            "Cost reduction visible in billing",
                            "No availability impact during scale-down",
                        ],
                        confidence=0.70,
                        service=utils[0].service,
                        current_state={
                            "replicas": current_replicas,
                            "autoscaling": "disabled",
                            "avg_utilization": avg_utilization,
                        },
                        proposed_state={
                            "minReplicas": min_replicas,
                            "maxReplicas": current_replicas + 2,
                            "targetCPUUtilization": 70,
                            "autoscaling": "enabled",
                        },
                    )
                )

        return recommendations

    async def generate_recommendations(self, evidence: CostEvidence) -> CostOptimizationReport:
        """Generate comprehensive cost optimization recommendations from evidence.

        Parameters
        ----------
        evidence
            Cost evidence bundle

        Returns
        -------
        CostOptimizationReport
            Complete cost optimization report
        """
        logger.info("Generating cost recommendations from evidence: %s", evidence.evidence_id)

        all_recommendations = []

        # Generate recommendations by category
        all_recommendations.extend(
            self.generate_rightsizing_recommendations(evidence.resource_utilization)
        )
        all_recommendations.extend(
            self.generate_idle_cleanup_recommendations(evidence.idle_resources)
        )
        all_recommendations.extend(
            self.generate_llm_optimization_recommendations(evidence.llm_usage)
        )
        all_recommendations.extend(
            self.generate_log_retention_recommendations(evidence.storage_metrics)
        )
        all_recommendations.extend(
            self.generate_autoscaling_recommendations(evidence.resource_utilization)
        )

        # Filter by confidence threshold
        filtered_recommendations = [
            rec for rec in all_recommendations if rec.confidence >= self.min_confidence
        ]

        # Calculate total potential savings
        total_savings = sum(
            rec.estimated_impact.monthly_savings_usd for rec in filtered_recommendations
        )

        # Extract analyzed services
        analyzed_services = []
        for util in evidence.resource_utilization:
            if util.service not in analyzed_services:
                analyzed_services.append(util.service)

        report_id = f"cost-report-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"

        # Determine analysis period from evidence
        # For now, assume 7 days
        from datetime import timedelta

        analysis_end = evidence.collected_at
        analysis_start = analysis_end - timedelta(days=7)

        logger.info(
            "Generated %d recommendations with total potential savings: $%.2f/month",
            len(filtered_recommendations),
            total_savings,
        )

        return CostOptimizationReport(
            report_id=report_id,
            generated_at=datetime.now(tz=UTC),
            analysis_period_start=analysis_start,
            analysis_period_end=analysis_end,
            evidence_summary=evidence,
            recommendations=filtered_recommendations,
            total_potential_monthly_savings=total_savings,
            total_current_monthly_cost=evidence.total_estimated_monthly_cost,
            analyzed_services=analyzed_services
            or [ServiceRef(name="unknown", environment=Environment.PRODUCTION)],
        )
