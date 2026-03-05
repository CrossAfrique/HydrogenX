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


class PortfolioOutput(BaseModel):
    """Portfolio calculation output - aggregated results across multiple sites"""
    portfolio_name: str = Field(..., description="Portfolio name")
    timestamp: datetime = Field(default_factory=datetime.utcnow,
                               description="Calculation timestamp")

    # Individual site results
    sites: List[SingleSiteOutput] = Field(..., description="Results for each site")

    # Aggregated portfolio metrics
    total_capex_usd: float = Field(..., description="Total portfolio CAPEX in USD")
    total_annual_opex_usd: float = Field(..., description="Total portfolio annual OPEX in USD")
    total_annual_revenue_usd: float = Field(..., description="Total portfolio annual revenue in USD")
    total_annual_ebitda_usd: float = Field(..., description="Total portfolio annual EBITDA in USD")
    
    # Portfolio financial metrics
    portfolio_irr_percent: float = Field(..., description="Portfolio blended IRR in %")
    portfolio_npv_usd: float = Field(default=None, description="Portfolio NPV in USD (optional)")
    
    # Aggregated monthly data for charting
    monthly_data: List[MonthlyDataPoint] = Field(...,
                                                  description="Aggregated 12-month revenue vs OPEX data")
