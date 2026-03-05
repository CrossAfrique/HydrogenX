"""
Pydantic models for HydrogenX API
Load-centric architecture: all sizing derives from daily load and autonomy hours
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ================== LOAD-CENTRIC INPUT MODELS ==================

class TechSpecificationsInput(BaseModel):
    """Technical specifications for all components"""
    # Battery specifications
    battery_usable_ratio: float = Field(default=0.8, ge=0.5, le=1.0,
                                       description="Usable capacity ratio (accounting for reserve SOC)")
    battery_power_rating_kw: float = Field(default=10.0, gt=0,
                                          description="Battery discharge power rating in kW")
    battery_efficiency_percent: float = Field(default=92, ge=80, le=99,
                                             description="Battery round-trip efficiency in %")
    
    # Hydrogen specifications
    electrolyzer_efficiency_percent: float = Field(default=75, ge=60, le=85,
                                                  description="Electrolyzer electrical efficiency in %")
    electrolyzer_heat_recovery_percent: float = Field(default=30, ge=0, le=50,
                                                     description="Heat recovery from electrolyzer in %")
    fuel_cell_efficiency_percent: float = Field(default=60, ge=40, le=75,
                                               description="Fuel cell electrical efficiency in %")
    h2_storage_pressure_bar: float = Field(default=350, ge=100, le=700,
                                          description="H2 storage pressure in bar")
    
    # PV/Energy specifications
    pv_performance_ratio: float = Field(default=0.85, ge=0.75, le=0.95,
                                       description="PV system performance ratio")
    peak_sun_hours_per_day: float = Field(default=4.5, ge=2.0, le=7.0,
                                         description="Peak sun hours per day for location")


class GlobalParametersInput(BaseModel):
    """Global financial and operational parameters"""
    discount_rate_percent: float = Field(default=8, ge=0, le=30,
                                        description="Discount rate in %")
    inflation_percent: float = Field(default=2.5, ge=0, le=10,
                                    description="Annual inflation rate in %")
    subsidy_percent: float = Field(default=0, ge=0, le=100,
                                  description="CAPEX subsidy in % of total CAPEX")
    
    # Pricing for revenue streams
    electricity_price_usd_per_kwh: float = Field(default=0.12, gt=0,
                                                description="Grid electricity price in USD/kWh")
    h2_price_usd_per_kg: float = Field(default=3.0, gt=0,
                                      description="Hydrogen selling price in USD/kg")
    heat_price_usd_per_kwh: float = Field(default=0.08, gt=0,
                                         description="Heat selling price in USD/kWh (from electrolyzer)")
    oxygen_price_usd_per_kg: float = Field(default=0.1, gt=0,
                                          description="Oxygen byproduct price in USD/kg")
    
    # Operational parameters
    project_lifetime_years: int = Field(default=25, ge=10, le=50,
                                       description="Project lifetime in years")
    operation_days_per_year: int = Field(default=330, ge=200, le=365,
                                        description="Annual operating days (excluding maintenance)")


class SingleSiteInput(BaseModel):
    """Single site calculation input - LOAD-CENTRIC ARCHITECTURE
    
    All other sizing derives from these three primary inputs:
    1. daily_load_kw: The facility's average daily load requirement
    2. battery_autonomy_hours: Hours of battery-only operation during outages
    3. hydrogen_autonomy_hours: Hours of additional H2 fuel cell operation
    """
    site_name: Optional[str] = Field(default="Site 1", description="Site name")
    
    # ===== PRIMARY DRIVERS (everything else derives from these) =====
    daily_load_kw: float = Field(..., gt=0,
                                description="Daily average load requirement in kW")
    battery_autonomy_hours: float = Field(..., gt=0,
                                         description="Hours of battery-only autonomy required")
    hydrogen_autonomy_hours: float = Field(..., ge=0,
                                          description="Additional hours of H2 fuel cell autonomy")
    
    # Technical specifications (with sensible defaults)
    tech_specs: TechSpecificationsInput = Field(default_factory=TechSpecificationsInput,
                                               description="Technical specifications for all components")
    
    # Global financial and operational parameters
    global_params: GlobalParametersInput = Field(default_factory=GlobalParametersInput,
                                               description="Global financial parameters")


class PortfolioInput(BaseModel):
    """Portfolio calculation input - array of sites with optional global parameter override"""
    sites: List[SingleSiteInput] = Field(..., min_items=1,
                                        description="Array of sites for portfolio analysis")
    portfolio_name: Optional[str] = Field(default="Portfolio",
                                         description="Portfolio name")


# ================== OUTPUT MODELS ==================


class SizingOutput(BaseModel):
    """System sizing results - all derived from daily load and autonomy hours"""
    # Daily consumption
    daily_consumption_kwh: float = Field(..., description="Daily energy consumption in kWh")
    
    # Battery sizing
    battery_capacity_kwh: float = Field(..., description="Battery gross capacity in kWh")
    battery_power_rating_kw: float = Field(..., description="Battery power rating in kW")
    battery_usable_kwh: float = Field(..., description="Battery usable capacity in kWh")
    
    # Hydrogen / Fuel Cell sizing
    h2_daily_production_kg: float = Field(..., description="Daily hydrogen production in kg")
    h2_storage_capacity_kg: float = Field(..., description="H2 storage capacity in kg")
    electrolyzer_capacity_kw: float = Field(..., description="Electrolyzer power rating in kW")
    fuel_cell_capacity_kw: float = Field(..., description="Fuel cell power rating in kW")
    
    # PV sizing
    pv_capacity_kwp: float = Field(..., description="PV array capacity in kWp")


class CapexBreakdownOutput(BaseModel):
    """CAPEX breakdown by component (all costs in USD)"""
    pv_capex_usd: float = Field(..., description="PV system CAPEX")
    battery_capex_usd: float = Field(..., description="Battery storage CAPEX")
    electrolyzer_capex_usd: float = Field(..., description="Electrolyzer system CAPEX")
    h2_storage_capex_usd: float = Field(..., description="H2 storage tank CAPEX")
    fuel_cell_capex_usd: float = Field(..., description="Fuel cell system CAPEX")
    balance_of_plant_capex_usd: float = Field(..., description="Balance of Plant (controls, infrastructure) CAPEX")
    total_capex_before_subsidy_usd: float = Field(..., description="Total CAPEX before subsidy")
    subsidy_usd: float = Field(..., description="Applied subsidy amount in USD")
    total_capex_after_subsidy_usd: float = Field(..., description="Total CAPEX after subsidy")


class OpexBreakdownOutput(BaseModel):
    """OPEX breakdown split into two groups for inflation modeling"""
    pv_battery_opex_usd_per_year: float = Field(...,
                                               description="Group 1: PV + Battery annual O&M")
    electrolyzer_fc_opex_usd_per_year: float = Field(...,
                                                    description="Group 2: Electrolyzer + Fuel Cell annual O&M")
    h2_storage_bop_opex_usd_per_year: float = Field(...,
                                                    description="Group 3: H2 Storage + Balance of Plant annual O&M")
    total_opex_usd_per_year: float = Field(...,
                                          description="Total annual OPEX (sum of all groups)")


class RevenueStreamsOutput(BaseModel):
    """Annual revenue streams from all sources"""
    h2_sales_revenue_usd_per_year: float = Field(...,
                                                description="Hydrogen sales revenue in USD/year")
    electricity_sales_revenue_usd_per_year: float = Field(...,
                                                        description="Excess electricity sales in USD/year")
    heat_recovery_revenue_usd_per_year: float = Field(...,
                                                     description="Heat recovery revenue in USD/year")
    oxygen_byproduct_revenue_usd_per_year: float = Field(...,
                                                        description="Oxygen byproduct sales (8 kg O2 per kg H2) in USD/year")
    total_revenue_usd_per_year: float = Field(...,
                                             description="Total annual revenue from all streams")


class FinancialMetricsOutput(BaseModel):
    """Financial metrics"""
    lcoe_usd_per_kwh: float = Field(..., description="LCOE in USD/kWh")
    lcoh_usd_per_kg: float = Field(..., description="LCOH in USD/kg H2")
    irr_percent: float = Field(..., description="IRR in %")
    npv_usd: float = Field(..., description="NPV in USD")
    payback_period_years: float = Field(..., description="Payback period in years")
    ebitda_usd_per_year: float = Field(..., description="Annual EBITDA in USD")


class MonthlyDataPoint(BaseModel):
    """Monthly revenue vs OPEX data point for charting"""
    month: int = Field(..., ge=1, le=12, description="Month number (1-12)")
    h2_revenue: float = Field(..., description="Monthly hydrogen sales revenue in USD")
    electricity_revenue: float = Field(..., description="Monthly electricity sales revenue in USD")
    heat_revenue: float = Field(..., description="Monthly heat recovery revenue in USD")
    oxygen_revenue: float = Field(..., description="Monthly oxygen byproduct revenue in USD")
    total_revenue: float = Field(..., description="Total monthly revenue in USD")
    total_opex: float = Field(..., description="Total monthly OPEX in USD")
    ebitda: float = Field(..., description="Monthly EBITDA (revenue - OPEX) in USD")


class SingleSiteOutput(BaseModel):
    """Single site calculation output"""
    site_name: str = Field(..., description="Site name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, 
                               description="Calculation timestamp")
    
    # Results
    sizing: SizingOutput
    capex_breakdown: CapexBreakdownOutput
    opex_breakdown: OpexBreakdownOutput
    revenue_streams: RevenueStreamsOutput
    financial_metrics: FinancialMetricsOutput
    monthly_data: List[MonthlyDataPoint] = Field(..., 
                                                description="12 months of revenue vs OPEX data")


class PortfolioOutput(BaseModel):
    """Portfolio calculation output - aggregated results across multiple sites"""
    portfolio_name: str = Field(..., description="Portfolio name")
    timestamp: datetime = Field(default_factory=datetime.utcnow,
                               description="Calculation timestamp")

    # Individual site results
    sites: List['SingleSiteOutput'] = Field(..., description="Results for each site")

    # Aggregated portfolio metrics
    total_capex_usd: float = Field(..., description="Total portfolio CAPEX in USD")
    total_annual_opex_usd: float = Field(..., description="Total portfolio annual OPEX in USD")
    total_annual_revenue_usd: float = Field(..., description="Total portfolio annual revenue in USD")
    total_annual_ebitda_usd: float = Field(..., description="Total portfolio annual EBITDA in USD")
    
    # Portfolio financial metrics
    portfolio_irr_percent: float = Field(..., description="Portfolio blended IRR in %")
    portfolio_npv_usd: float = Field(default=None, description="Portfolio NPV in USD (optional)")
    
    # Aggregated monthly data for charting
    monthly_data: List['MonthlyDataPoint'] = Field(...,
                                                   description="Aggregated 12-month revenue vs OPEX data")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, 
                               description="Check timestamp")
