"""
Output Pydantic models for HydrogenX calculations.
Split from schemas to keep input and output concerns separate.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

# import input-related models where necessary for reuse
from models.schemas import (
    SizingOutput,
    CapexBreakdownOutput,
    OpexBreakdownOutput,
    RevenueStreamsOutput,
    FinancialMetricsOutput,
    MonthlyDataPoint,
)


class SensitivityScenario(BaseModel):
    """Individual sensitivity case"""
    description: str = Field(..., description="Human-readable scenario label")
    financial_metrics: FinancialMetricsOutput


class SingleSiteOutput(BaseModel):
    """Single site calculation output"""
    site_name: str = Field(..., description="Site name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Calculation timestamp")

    # core results
    sizing: SizingOutput
    capex_breakdown: CapexBreakdownOutput
    opex_breakdown: OpexBreakdownOutput
    revenue_streams: RevenueStreamsOutput
    financial_metrics: FinancialMetricsOutput
    monthly_data: List[MonthlyDataPoint] = Field(..., description="12 months of revenue vs OPEX data")

    # analysis helpers
    sensitivity: List[SensitivityScenario] = Field(..., description="Sensitivity results for key parameters")


# future portfolio models will go here
