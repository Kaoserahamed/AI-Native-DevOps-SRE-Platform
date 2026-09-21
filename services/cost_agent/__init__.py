"""Cost optimization agent service.

This agent analyzes resource utilization, identifies cost optimization opportunities,
and generates non-mutating recommendations with estimated impact.
"""

from __future__ import annotations

__all__ = ["CostCollector", "CostRecommender"]

from services.cost_agent.collector import CostCollector
from services.cost_agent.recommender import CostRecommender
