"""
Pydantic models for HydrogenX API
Load-centric architecture: all sizing derives from daily load and autonomy hours
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ================== LOAD-CENTRIC INPUT MODELS ==================

class LoadAutonomyInput(BaseModel):
    """Project Load & Autonomy parameters"""
    daily_load_kwh: float = Field(default=192.0, gt=0, description="Daily Load (kWh/day)")
    site_load_kw: float = Field(default=None, gt=0,
                                description="Site Load (kW) - average power. If provided, overrides daily_load_kwh conversion")
    battery_autonomy_hours: float = Field(default=12.0, gt=0,
                                         description="Battery Autonomy (hours)")
    hydrogen_autonomy_hours: float = Field(default=5.0, ge=0,
                                          description="Hydrogen Autonomy (hours)")
    electrolyzer_charge_window_hours: float = Field(default=5.0, gt=0,
                                                   description="Electrolyzer Charge Window (hours)")


class EfficienciesConstantsInput(BaseModel):
    """Efficiencies & Constants parameters"""
    battery_dod_percent: float = Field(default=80.0, ge=0, le=100,
                                      description="Battery DoD (%)")
    battery_efficiency_percent: float = Field(default=90.0, ge=80, le=99,
                                             description="Battery Efficiency (%)")
    fuel_cell_efficiency_percent: float = Field(default=50.0, ge=40, le=75,
                                               description="Fuel Cell Efficiency (%)")
    electrolyzer_efficiency_percent: float = Field(default=70.0, ge=60, le=85,
                                                  description="Electrolyzer Efficiency (%)")
    hydrogen_lhv_kwh_per_kg: float = Field(default=33.3, gt=0,
                                          description="Hydrogen LHV (kWh/kg)")
    pv_efficiency_factor: float = Field(default=1.2, gt=0,
                                       description="PV Efficiency Factor")
    jan_average_psh: float = Field(default=5.1, ge=0,
                                  description="Jan Average PSH")
    august_average_psh: float = Field(default=3.3, ge=0,
                                     description="August Average PSH")


class SizingSafetyFactorsInput(BaseModel):
    """Sizing Safety Factors parameters"""
    pv_oversizing_factor: float = Field(default=1.0, gt=0,
                                       description="Oversizing Factor for PV (set to 1.0 to match common Excel reference models)")
    safety_margin_general: float = Field(default=1.1, gt=0,
                                        description="Safety Margin (general)")


class FinancialAssumptionsInput(BaseModel):
    """Financial Assumptions parameters"""
    discount_rate_percent: float = Field(default=10.0, ge=0, le=30,
                                        description="Discount Rate (%)")
    system_lifetime_years: float = Field(default=15.0, ge=10, le=50,
                                        description="System Lifetime (years)")
    eaas_contract_years: float = Field(default=10.0, gt=0,
                                      description="EaaS Contract (years)")
    capex_subsidy_percent: float = Field(default=30.0, ge=0, le=100,
                                        description="CAPEX Subsidy (%)")
    opex_rate_pv_battery_percent: float = Field(default=2.0, ge=0,
                                               description="OPEX Rate PV/Battery (%)")
    opex_rate_electrolyzer_fc_percent: float = Field(default=3.0, ge=0,
                                                    description="OPEX Rate Electrolyzer/Fuel Cell (%)")
    opex_inflation_percent: float = Field(default=2.0, ge=0, le=10,
                                         description="OPEX Inflation (%)")
    revenue_growth_percent: float = Field(default=2.0, ge=0,
                                         description="Revenue Growth (%)")
    diesel_lcoe_usd_per_kwh: float = Field(default=0.356, gt=0,
                                          description="Diesel LCOE ($/kWh)")
    eaas_price_usd_per_kwh: float = Field(default=0.267, gt=0,
                                         description="EaaS Price ($/kWh)")
    units_deployed: int = Field(default=1, gt=0,
                               description="Units Deployed")


class CostParametersInput(BaseModel):
    """Cost Parameters"""
    solar_pv_cost_usd_per_kwp: float = Field(default=650.0, gt=0,
                                            description="Solar PV Cost ($/kWp)")
    battery_cost_usd_per_kwh: float = Field(default=250.0, gt=0,
                                           description="Battery Cost ($/kWh)")
    fuel_cell_cost_usd_per_kw: float = Field(default=1000.0, gt=0,
                                            description="Fuel Cell Cost ($/kW)")
    electrolyzer_cost_usd_per_kw: float = Field(default=800.0, gt=0,
                                               description="Electrolyzer Cost ($/kW)")
    oxygen_production_ratio_kg_per_kg: float = Field(default=8.0, gt=0,
                                                    description="Oxygen Production Ratio (kg O2/kg H2)")
    oxygen_price_usd_per_kg: float = Field(default=0.3, gt=0,
                                          description="Oxygen Price ($/kg)")
    area_m2: float = Field(default=6.0, gt=0,
                          description="Area (M^2)")


class TechSpecsInput(BaseModel):
    """Technical Specifications parameters"""
    battery_usable_ratio: float = Field(default=0.8, ge=0, le=1,
                                       description="Battery Usable Ratio (DoD)")
    battery_efficiency_percent: float = Field(default=90.0, ge=80, le=99,
                                             description="Battery Efficiency (%)")
    fuel_cell_efficiency_percent: float = Field(default=50.0, ge=40, le=75,
                                               description="Fuel Cell Efficiency (%)")
    electrolyzer_efficiency_percent: float = Field(default=70.0, ge=60, le=85,
                                                  description="Electrolyzer Efficiency (%)")
    pv_performance_ratio: float = Field(default=1.2, gt=0,
                                       description="PV Performance Ratio")
    peak_sun_hours_per_day: float = Field(default=4.2, ge=0,
                                         description="Peak Sun Hours per Day")


class GlobalParamsInput(BaseModel):
    """Global Parameters"""
    discount_rate_percent: float = Field(default=10.0, ge=0, le=30,
                                        description="Discount Rate (%)")
    inflation_percent: float = Field(default=2.0, ge=0, le=10,
                                    description="Inflation (%)")
    subsidy_percent: float = Field(default=30.0, ge=0, le=100,
                                  description="Subsidy (%)")
    eaas_price_usd_per_kwh: float = Field(default=0.267, gt=0,
                                         description="EaaS Price ($/kWh)")
    project_lifetime_years: float = Field(default=15.0, ge=10, le=50,
                                        description="Project Lifetime (years)")
    operation_days_per_year: int = Field(default=365, ge=0, le=365,
                                        description="Operation Days per Year")


class SingleSiteInput(BaseModel):
    """Single site calculation input - LOAD-CENTRIC ARCHITECTURE
    
    All other sizing derives from these three primary inputs:
    1. daily_load_kwh: The facility's average daily load requirement
    2. battery_autonomy_hours: Hours of battery-only operation during outages
    3. hydrogen_autonomy_hours: Hours of additional H2 fuel cell operation
    """
    site_name: Optional[str] = Field(default="Site 1", description="Site name")
    
    # Frontend-compatible top-level fields
    daily_load_kw: Optional[float] = Field(default=None, gt=0, description="Site Load (kW) - average power")
    battery_autonomy_hours: Optional[float] = Field(default=None, gt=0, description="Battery Autonomy (hours)")
    hydrogen_autonomy_hours: Optional[float] = Field(default=None, ge=0, description="Hydrogen Autonomy (hours)")
    tech_specs: Optional[TechSpecsInput] = Field(default=None, description="Technical Specifications")
    global_params: Optional[GlobalParamsInput] = Field(default=None, description="Global Parameters")
    
    # ===== PRIMARY DRIVERS (everything else derives from these) =====
    load_autonomy: LoadAutonomyInput = Field(default_factory=LoadAutonomyInput,
                                             description="Project Load & Autonomy parameters")
    efficiencies_constants: EfficienciesConstantsInput = Field(default_factory=EfficienciesConstantsInput,
                                                               description="Efficiencies & Constants parameters")
    sizing_safety_factors: SizingSafetyFactorsInput = Field(default_factory=SizingSafetyFactorsInput,
                                                           description="Sizing Safety Factors parameters")
    financial_assumptions: FinancialAssumptionsInput = Field(default_factory=FinancialAssumptionsInput,
                                                            description="Financial Assumptions parameters")
    cost_parameters: CostParametersInput = Field(default_factory=CostParametersInput,
                                                 description="Cost Parameters")


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
    pv_area_m2: float = Field(..., description="PV array area in m^2")


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
    discounted_revenue_usd: float = Field(..., description="Discounted revenue over contract years")
    discounted_opex_usd: float = Field(..., description="Discounted opex over system lifetime")
    discounted_energy_kwh: float = Field(..., description="Discounted energy production over system lifetime")
    total_discounted_cost_usd: float = Field(..., description="Total discounted cost (capex + opex)")
    cash_flow_usd: List[float] = Field(..., description="Annual cash flow series (year 0 first)")


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
