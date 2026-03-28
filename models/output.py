"""
Output Pydantic models for HydrogenX calculations.
Split from schemas to keep input and output concerns separate.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

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
    name: str = Field(..., description="Scenario name")
    description: Optional[str] = Field(None, description="Optional scenario description")
    financial_metrics: FinancialMetricsOutput


class HourlySnapshot(BaseModel):
    """Hourly simulation snapshot for energy balance and component dispatch."""
    hour: int = Field(..., ge=0, le=8759, description="Hour index in the year")
    pv_production_kwh: float = Field(..., description="PV energy produced during the hour")
    load_kwh: float = Field(..., description="Site load during the hour")
    battery_soc_kwh: float = Field(..., description="Battery state of charge at the end of the hour")
    battery_charge_kwh: float = Field(..., description="Battery charge energy during the hour")
    battery_discharge_kwh: float = Field(..., description="Battery discharge energy during the hour")
    h2_produced_kg: float = Field(..., description="Hydrogen produced during the hour")
    h2_consumed_kg: float = Field(..., description="Hydrogen consumed by the fuel cell during the hour")
    h2_stored_kg: float = Field(..., description="Hydrogen storage level at the end of the hour")
    electrolyzer_dispatch_kwh: float = Field(..., description="Electrolyzer electrical dispatch during the hour")
    fuel_cell_dispatch_kwh: float = Field(..., description="Fuel cell electrical dispatch during the hour")
    excess_export_kwh: float = Field(..., description="Excess electricity exported to grid during the hour")


class OptimizationResult(BaseModel):
    """Optimization result for best sizing variables."""
    optimal_battery_autonomy_hours: float = Field(..., description="Best battery autonomy hours")
    optimal_hydrogen_autonomy_hours: float = Field(..., description="Best hydrogen autonomy hours")
    optimal_lcoe_usd_per_kwh: float = Field(..., description="Minimum LCOE achieved")
    optimal_irr_percent: float = Field(..., description="IRR at optimum sizing")
    optimal_npv_usd: float = Field(..., description="NPV at optimum sizing")
    optimal_payback_period_years: float = Field(..., description="Payback period at optimum sizing")
    optimization_success: bool = Field(..., description="Whether optimization converged successfully")
    optimization_message: str = Field(..., description="Optimization solver message")


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
