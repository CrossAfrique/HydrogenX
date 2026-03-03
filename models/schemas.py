"""
Pydantic models for HydrogenX API
Includes input/output models for single-site and portfolio calculations
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class ThermalBaseloadInput(BaseModel):
    """Thermal Baseload parameters"""
    capacity_kwth: float = Field(..., gt=0, description="Thermal baseload capacity in kWth")


class SolarPVInput(BaseModel):
    """Solar PV parameters"""
    capacity_kwp: float = Field(..., gt=0, description="PV capacity in kWp")
    performance_ratio: float = Field(default=0.85, ge=0.7, le=1.0, 
                                     description="PV performance ratio (0.7-1.0)")


class BatteryStorageInput(BaseModel):
    """Battery Storage parameters"""
    capacity_kwh: float = Field(..., gt=0, description="Battery capacity in kWh")
    power_rating_kw: float = Field(..., gt=0, description="Battery discharge power rating in kW")
    reserve_soc_percent: float = Field(default=20, ge=0, le=100, 
                                       description="Reserve state of charge in %")
    autonomy_hours: Optional[float] = Field(default=4, gt=0, 
                                           description="Battery autonomy hours")


class ElectrolyzerInput(BaseModel):
    """Electrolyzer parameters"""
    power_kw: float = Field(..., gt=0, description="Electrolyzer rated power in kW")
    specific_energy_kwh_per_kg: float = Field(default=50, gt=0, 
                                             description="Specific energy consumption in kWh/kg H2")
    heat_recovery_percent: float = Field(default=30, ge=0, le=100, 
                                        description="Heat recovery percentage")


class HydrogenStorageInput(BaseModel):
    """Hydrogen Storage parameters"""
    capacity_kg: float = Field(..., gt=0, description="H2 storage capacity in kg")
    autonomy_hours: Optional[float] = Field(default=24, gt=0, 
                                           description="H2 storage autonomy hours")


class FuelCellInput(BaseModel):
    """Fuel Cell parameters"""
    power_rating_kw: float = Field(..., gt=0, description="Fuel cell power rating in kW")
    efficiency_percent: float = Field(default=60, ge=30, le=90, 
                                     description="Fuel cell efficiency in %")


class GeneratorGridInput(BaseModel):
    """Generator & Grid parameters"""
    generator_capacity_kw: float = Field(..., ge=0, description="Generator capacity in kW")
    grid_import_limit_kw: float = Field(..., ge=0, description="Grid import limit in kW")


class GlobalParametersInput(BaseModel):
    """Global financial and operational parameters"""
    discount_rate_percent: float = Field(default=8, ge=0, le=30, 
                                        description="Discount rate in %")
    inflation_percent: float = Field(default=2.5, ge=0, le=10, 
                                    description="Inflation rate in %")
    subsidy_percent: float = Field(default=0, ge=0, le=100, 
                                  description="CAPEX subsidy in %")
    electricity_price_usd_per_kwh: float = Field(default=0.12, gt=0, 
                                                description="Grid electricity price in USD/kWh")
    h2_price_usd_per_kg: float = Field(default=3.0, gt=0, 
                                      description="Hydrogen selling price in USD/kg")
    heat_price_usd_per_kwh: float = Field(default=0.08, gt=0, 
                                         description="Heat selling price in USD/kWh")
    oxygen_price_usd_per_kg: float = Field(default=0.1, gt=0, 
                                          description="Oxygen selling price in USD/kg")
    project_lifetime_years: int = Field(default=25, ge=10, le=50, 
                                       description="Project lifetime in years")
    operation_days_per_year: int = Field(default=330, ge=200, le=365, 
                                        description="Operation days per year")
    peak_sun_hours_per_day: float = Field(default=4.5, ge=2.0, le=7.0, 
                                         description="Peak sun hours per day (2.0-7.0, varies by location)")


class SingleSiteInput(BaseModel):
    """Single site calculation input"""
    site_name: Optional[str] = Field(default="Site 1", description="Site name")
    
    # Component parameters
    thermal_baseload: ThermalBaseloadInput
    solar_pv: SolarPVInput
    battery_storage: BatteryStorageInput
    electrolyzer: ElectrolyzerInput
    hydrogen_storage: HydrogenStorageInput
    fuel_cell: FuelCellInput
    generator_grid: GeneratorGridInput
    
    # Global parameters
    global_params: GlobalParametersInput


class PortfolioInput(BaseModel):
    """Portfolio calculation input (array of sites)"""
    sites: List[SingleSiteInput] = Field(..., min_items=1, 
                                        description="Array of sites for portfolio analysis")
    portfolio_name: Optional[str] = Field(default="Portfolio", 
                                         description="Portfolio name")
    global_params: Optional[GlobalParametersInput] = Field(
        default=None, 
        description="Global parameters override for entire portfolio"
    )


# ================== OUTPUT MODELS ==================


class SizingOutput(BaseModel):
    """System sizing results"""
    pv_capacity_kwp: float = Field(..., description="Sized PV capacity in kWp")
    battery_capacity_kwh: float = Field(..., description="Sized battery capacity in kWh")
    electrolyzer_capacity_kw: float = Field(..., description="Sized electrolyzer capacity in kW")
    h2_storage_capacity_kg: float = Field(..., description="Sized H2 storage capacity in kg")
    fuel_cell_capacity_kw: float = Field(..., description="Sized fuel cell capacity in kW")


class CapexBreakdownOutput(BaseModel):
    """CAPEX breakdown by component"""
    pv_capex_usd: float = Field(..., description="PV CAPEX in USD")
    battery_capex_usd: float = Field(..., description="Battery CAPEX in USD")
    electrolyzer_capex_usd: float = Field(..., description="Electrolyzer CAPEX in USD")
    h2_storage_capex_usd: float = Field(..., description="H2 storage CAPEX in USD")
    fuel_cell_capex_usd: float = Field(..., description="Fuel cell CAPEX in USD")
    bop_capex_usd: float = Field(..., description="Balance of Plant CAPEX in USD")
    total_capex_usd: float = Field(..., description="Total CAPEX in USD")
    after_subsidy_capex_usd: float = Field(..., description="CAPEX after subsidy in USD")


class OpexBreakdownOutput(BaseModel):
    """OPEX breakdown"""
    pv_battery_opex_usd_per_year: float = Field(..., 
                                               description="PV + Battery O&M in USD/year")
    electrolyzer_fc_opex_usd_per_year: float = Field(..., 
                                                    description="Electrolyzer + Fuel Cell O&M in USD/year")
    total_opex_usd_per_year: float = Field(..., 
                                          description="Total OPEX in USD/year")


class RevenueStreamsOutput(BaseModel):
    """Annual revenue streams"""
    electricity_revenue_usd_per_year: float = Field(..., 
                                                   description="Electricity revenue in USD/year")
    heat_revenue_usd_per_year: float = Field(..., 
                                            description="Heat revenue in USD/year")
    oxygen_revenue_usd_per_year: float = Field(..., 
                                              description="Oxygen revenue in USD/year")
    total_revenue_usd_per_year: float = Field(..., 
                                             description="Total annual revenue in USD/year")


class FinancialMetricsOutput(BaseModel):
    """Financial metrics"""
    lcoe_usd_per_kwh: float = Field(..., description="LCOE in USD/kWh")
    lcoh_usd_per_kg: float = Field(..., description="LCOH in USD/kg H2")
    irr_percent: float = Field(..., description="IRR in %")
    npv_usd: float = Field(..., description="NPV in USD")
    payback_period_years: float = Field(..., description="Payback period in years")
    ebitda_usd_per_year: float = Field(..., description="Annual EBITDA in USD")


class MonthlyDataPoint(BaseModel):
    """Monthly revenue vs OPEX data point for chart"""
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    electricity_revenue: float = Field(..., description="Electricity revenue in USD")
    heat_revenue: float = Field(..., description="Heat revenue in USD")
    oxygen_revenue: float = Field(..., description="Oxygen revenue in USD")
    total_opex: float = Field(..., description="Total OPEX in USD")
    ebitda: float = Field(..., description="EBITDA (Total Revenue - OPEX) in USD")


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
    """Portfolio calculation output"""
    portfolio_name: str = Field(..., description="Portfolio name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, 
                               description="Calculation timestamp")
    
    # Individual site results
    sites: List[SingleSiteOutput] = Field(..., description="Results for each site")
    
    # Aggregated portfolio metrics
    total_capex_usd: float = Field(..., description="Total portfolio CAPEX in USD")
    total_opex_usd_per_year: float = Field(..., 
                                          description="Total portfolio annual OPEX in USD")
    total_revenue_usd_per_year: float = Field(..., 
                                             description="Total portfolio annual revenue in USD")
    total_ebitda_usd_per_year: float = Field(..., 
                                            description="Total portfolio annual EBITDA in USD")
    portfolio_irr_percent: float = Field(..., description="Portfolio IRR in %")
    portfolio_npv_usd: float = Field(..., description="Portfolio NPV in USD")
    
    # Aggregated monthly data
    monthly_data: List[MonthlyDataPoint] = Field(..., 
                                                description="12 months of aggregated data")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, 
                               description="Check timestamp")
