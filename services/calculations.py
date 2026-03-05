"""
HydrogenX Calculation Service - Load-Centric Architecture

Core principle: All sizing derives from three primary inputs:
1. Daily Load (kW)
2. Battery Autonomy (hours)
3. Hydrogen Autonomy (hours)

Everything else is automatically calculated from these values.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

import math

from models.schemas import SingleSiteInput, PortfolioInput
from models.output import (
    SingleSiteOutput,
    PortfolioOutput,
    SizingOutput,
    CapexBreakdownOutput,
    OpexBreakdownOutput,
    RevenueStreamsOutput,
    FinancialMetricsOutput,
    MonthlyDataPoint,
    SensitivityScenario,
)


class HydrogenCalculator:
    """Load-centric calculation engine for HydrogenX.
    
    All component sizing is derived from:
    - daily_load_kw: facility's average daily load
    - battery_autonomy_hours: hours of battery-only operation
    - hydrogen_autonomy_hours: hours of H2 fuel cell operation
    """

    # Cost data for components (USD units)
    COST_DATA = {
        "pv": {"capex_per_kwp": 800, "opex_percent_per_year": 0.5},
        "battery": {"capex_per_kwh": 300, "opex_percent_per_year": 1.0},
        "electrolyzer": {"capex_per_kw": 1200, "opex_percent_per_year": 2.0},
        "h2_storage": {"capex_per_kg": 50, "opex_percent_per_year": 1.5},
        "fuel_cell": {"capex_per_kw": 1500, "opex_percent_per_year": 2.5},
        "balance_of_plant": {"capex_percent": 15, "opex_percent_per_year": 1.0},
    }

    @classmethod
    def calculate_single_site(cls, input_data: SingleSiteInput) -> SingleSiteOutput:
        """Calculate single site with load-centric architecture.
        
        Flow:
        1. Derive component sizing from daily load and autonomy hours
        2. Calculate annual production and consumption
        3. Determine CAPEX and OPEX breakdown
        4. Calculate revenue streams
        5. Compute financial metrics
        6. Generate monthly data for charting
        7. Optional: sensitivity analysis
        """
        gp = input_data.global_params
        ts = input_data.tech_specs

        # === STEP 1: SIZING ===
        sizing = cls._calculate_sizing_from_load(
            daily_load_kw=input_data.daily_load_kw,
            battery_autonomy_hours=input_data.battery_autonomy_hours,
            hydrogen_autonomy_hours=input_data.hydrogen_autonomy_hours,
            tech_specs=ts,
            gp=gp,
        )

        # === STEP 2: CAPEX ===
        capex = cls._calculate_capex(sizing, gp)

        # === STEP 3: OPEX ===
        opex = cls._calculate_opex(sizing, capex)

        # === STEP 4: REVENUE ===
        revenue = cls._calculate_revenue(sizing, gp, ts)

        # === STEP 5: FINANCIAL METRICS ===
        financial = cls._calculate_financial_metrics(capex, opex, revenue, gp, ts)

        # === STEP 6: MONTHLY DATA ===
        monthly = cls._calculate_monthly_data(sizing, revenue, opex, gp)

        # === STEP 7: SENSITIVITY (optional) ===
        sensitivity = cls._calculate_sensitivity(sizing, capex, opex, revenue, gp, ts)

        return SingleSiteOutput(
            site_name=input_data.site_name or "Site 1",
            timestamp=datetime.utcnow(),
            sizing=sizing,
            capex_breakdown=capex,
            opex_breakdown=opex,
            revenue_streams=revenue,
            financial_metrics=financial,
            monthly_data=monthly,
            sensitivity=sensitivity,
        )

    @classmethod
    def calculate_portfolio(cls, input_data: PortfolioInput) -> PortfolioOutput:
        """Calculate portfolio aggregating multiple sites."""
        # Calculate each site individually
        site_outputs = []
        for site in input_data.sites:
            site_output = cls.calculate_single_site(site)
            site_outputs.append(site_output)

        # Aggregate metrics
        total_capex = sum(s.capex_breakdown.total_capex_after_subsidy_usd for s in site_outputs)
        total_opex = sum(s.opex_breakdown.total_opex_usd_per_year for s in site_outputs)
        total_revenue = sum(s.revenue_streams.total_revenue_usd_per_year for s in site_outputs)
        total_ebitda = total_revenue - total_opex

        # Aggregate monthly data
        monthly_data = cls._aggregate_monthly_data(site_outputs)

        # Portfolio IRR and NPV (simplified: weighted average)
        irr_avg = sum(s.financial_metrics.irr_percent for s in site_outputs) / len(site_outputs)
        npv_sum = sum(s.financial_metrics.npv_usd for s in site_outputs)

        return PortfolioOutput(
            portfolio_name=input_data.portfolio_name or "Portfolio",
            timestamp=datetime.utcnow(),
            sites=site_outputs,
            total_capex_usd=total_capex,
            total_annual_opex_usd=total_opex,
            total_annual_revenue_usd=total_revenue,
            total_annual_ebitda_usd=total_ebitda,
            portfolio_irr_percent=irr_avg,
            portfolio_npv_usd=npv_sum,
            monthly_data=monthly_data,
        )

    # ========== SIZING LOGIC ==========

    @classmethod
    def _calculate_sizing_from_load(
        cls,
        daily_load_kw: float,
        battery_autonomy_hours: float,
        hydrogen_autonomy_hours: float,
        tech_specs,
        gp,
    ) -> SizingOutput:
        """Derive all component sizing from daily load and autonomy hours.
        
        This is the core load-centric logic:
        - Daily consumption = daily_load_kw * 24 hours
        - Battery capacity sized for battery_autonomy_hours of autonomy
        - H2 storage sized for hydrogen_autonomy_hours of autonomy
        - Electrolyzer, fuel cell, and PV sized accordingly
        """

        # Daily consumption
        daily_consumption_kwh = daily_load_kw * 24

        # === BATTERY SIZING ===
        # Battery needs to provide 'battery_autonomy_hours' worth of energy
        # accounting for usable ratio (reserve SOC)
        battery_usable_needed = daily_load_kw * battery_autonomy_hours
        battery_gross_capacity = battery_usable_needed / tech_specs.battery_usable_ratio
        battery_power_rating = daily_load_kw * 1.5  # 50% headroom for peak loads

        # === HYDROGEN & FUEL CELL SIZING ===
        # H2 covers additional autonomy beyond battery
        # Electrolyzer efficiency: useful energy / electrical input
        electrolyzer_efficiency_decimal = tech_specs.electrolyzer_efficiency_percent / 100

        # Daily H2 production needed (assuming electrolyzer runs daily)
        # At 75% efficiency, ~50 kWh needed per kg of H2 produced
        kwh_per_kg_h2 = 50 / electrolyzer_efficiency_decimal
        h2_daily_kg = daily_consumption_kwh / kwh_per_kg_h2

        # H2 storage for the autonomy period
        h2_storage_capacity = h2_daily_kg * (hydrogen_autonomy_hours / 24) if hydrogen_autonomy_hours > 0 else 0

        # Fuel cell power rating = load that H2 needs to serve
        # Assuming fuel cell covers the hydrogen autonomy load
        fc_load_kw = daily_load_kw
        fuel_cell_power_rating = fc_load_kw * 1.2  # 20% headroom

        # Electrolyzer power rating
        # Must produce daily H2 production during available sunlight hours (peak_sun_hours)
        peak_sun_hours = tech_specs.peak_sun_hours_per_day
        h2_power_needed = h2_daily_kg * kwh_per_kg_h2 / peak_sun_hours
        electrolyzer_power_rating = h2_power_needed / electrolyzer_efficiency_decimal if peak_sun_hours > 0 else 0

        # === PV SIZING ===
        # PV must cover:
        # 1. Direct load consumption
        # 2. Battery charging losses
        # 3. Electrolyzer energy needs
        # 4. Efficiency losses

        battery_efficiency_decimal = tech_specs.battery_efficiency_percent / 100
        battery_charging_kwh = daily_consumption_kwh / battery_efficiency_decimal
        efficiency_loss_factor = 1.15  # 15% additional for system losses

        # Total daily PV energy needed
        electrolyzer_daily_kwh = h2_daily_kg * kwh_per_kg_h2
        pv_daily_energy_needed = (
            daily_consumption_kwh  # Direct load
            + (battery_charging_kwh - daily_consumption_kwh)  # Battery losses
            + electrolyzer_daily_kwh  # Electrolyzer demand
        ) * efficiency_loss_factor

        pv_performance_ratio = tech_specs.pv_performance_ratio
        pv_capacity_kwp = pv_daily_energy_needed / (peak_sun_hours * pv_performance_ratio) if peak_sun_hours > 0 else 0

        return SizingOutput(
            daily_consumption_kwh=daily_consumption_kwh,
            battery_capacity_kwh=battery_gross_capacity,
            battery_power_rating_kw=battery_power_rating,
            battery_usable_kwh=battery_usable_needed,
            h2_daily_production_kg=h2_daily_kg,
            h2_storage_capacity_kg=h2_storage_capacity,
            electrolyzer_capacity_kw=electrolyzer_power_rating,
            fuel_cell_capacity_kw=fuel_cell_power_rating,
            pv_capacity_kwp=pv_capacity_kwp,
        )


    # ========== COST CALCULATIONS ==========

    @classmethod
    def _calculate_capex(cls, sizing: SizingOutput, gp) -> CapexBreakdownOutput:
        """Calculate CAPEX breakdown from sized components."""
        c = cls.COST_DATA

        # Component costs
        pv_capex = sizing.pv_capacity_kwp * c["pv"]["capex_per_kwp"]
        battery_capex = sizing.battery_capacity_kwh * c["battery"]["capex_per_kwh"]
        electrolyzer_capex = sizing.electrolyzer_capacity_kw * c["electrolyzer"]["capex_per_kw"]
        h2_storage_capex = sizing.h2_storage_capacity_kg * c["h2_storage"]["capex_per_kg"]
        fuel_cell_capex = sizing.fuel_cell_capacity_kw * c["fuel_cell"]["capex_per_kw"]

        # Sum of all components
        component_sum = (
            pv_capex
            + battery_capex
            + electrolyzer_capex
            + h2_storage_capex
            + fuel_cell_capex
        )

        # Balance of Plant (15% of component sum)
        bop_capex = component_sum * (c["balance_of_plant"]["capex_percent"] / 100)
        total_capex = component_sum + bop_capex

        # Apply subsidy
        subsidy_amount = total_capex * (gp.subsidy_percent / 100)
        capex_after_subsidy = total_capex - subsidy_amount

        return CapexBreakdownOutput(
            pv_capex_usd=pv_capex,
            battery_capex_usd=battery_capex,
            electrolyzer_capex_usd=electrolyzer_capex,
            h2_storage_capex_usd=h2_storage_capex,
            fuel_cell_capex_usd=fuel_cell_capex,
            balance_of_plant_capex_usd=bop_capex,
            total_capex_before_subsidy_usd=total_capex,
            subsidy_usd=subsidy_amount,
            total_capex_after_subsidy_usd=capex_after_subsidy,
        )

    @classmethod
    def _calculate_opex(cls, sizing: SizingOutput, capex: CapexBreakdownOutput) -> OpexBreakdownOutput:
        """Calculate annual OPEX split into three groups."""
        c = cls.COST_DATA

        # Group 1: PV + Battery O&M
        pv_battery_opex = (
            capex.pv_capex_usd * (c["pv"]["opex_percent_per_year"] / 100)
            + capex.battery_capex_usd * (c["battery"]["opex_percent_per_year"] / 100)
        )

        # Group 2: Electrolyzer + Fuel Cell O&M
        elec_fc_opex = (
            capex.electrolyzer_capex_usd * (c["electrolyzer"]["opex_percent_per_year"] / 100)
            + capex.fuel_cell_capex_usd * (c["fuel_cell"]["opex_percent_per_year"] / 100)
        )

        # Group 3: H2 Storage + Balance of Plant O&M
        h2_bop_opex = (
            capex.h2_storage_capex_usd * (c["h2_storage"]["opex_percent_per_year"] / 100)
            + capex.balance_of_plant_capex_usd * (c["balance_of_plant"]["opex_percent_per_year"] / 100)
        )

        total_opex = pv_battery_opex + elec_fc_opex + h2_bop_opex

        return OpexBreakdownOutput(
            pv_battery_opex_usd_per_year=pv_battery_opex,
            electrolyzer_fc_opex_usd_per_year=elec_fc_opex,
            h2_storage_bop_opex_usd_per_year=h2_bop_opex,
            total_opex_usd_per_year=total_opex,
        )


    # ========== REVENUE CALCULATIONS ==========

    @classmethod
    def _calculate_revenue(cls, sizing: SizingOutput, gp, tech_specs) -> RevenueStreamsOutput:
        """Calculate annual revenue from all streams.
        
        Revenue sources:
        1. H2 sales at specified price
        2. Excess electricity sales
        3. Heat recovery from electrolyzer
        4. Oxygen byproduct (8 kg O2 per kg H2)
        """
        # Daily production values
        h2_daily_kg = sizing.h2_daily_production_kg
        operation_days = gp.operation_days_per_year

        # Annual production
        h2_annual_kg = h2_daily_kg * operation_days
        
        # Oxygen byproduct: 8 kg O2 per kg H2
        o2_annual_kg = h2_annual_kg * 8

        # H2 Sales Revenue
        h2_revenue = h2_annual_kg * gp.h2_price_usd_per_kg

        # Electricity sales (simplified: small percentage of PV production available for export)
        pv_daily_kwh = sizing.pv_capacity_kwp * tech_specs.peak_sun_hours_per_day
        pv_annual_kwh = pv_daily_kwh * operation_days
        
        # Assume 10% excess available after load and H2 production
        excess_electricity_kwh = pv_annual_kwh * 0.10
        electricity_revenue = excess_electricity_kwh * gp.electricity_price_usd_per_kwh

        # Heat recovery from electrolyzer
        # Heat available = PV energy * heat recovery % - thermalLoad
        pv_energy_for_heat = pv_annual_kwh * (1 - 0.75)  # 75% goes to H2, 25% available
        heat_available_kwh = pv_energy_for_heat
        heat_revenue = heat_available_kwh * gp.heat_price_usd_per_kwh

        # Oxygen sales
        oxygen_revenue = o2_annual_kg * gp.oxygen_price_usd_per_kg

        total_revenue = h2_revenue + electricity_revenue + heat_revenue + oxygen_revenue

        return RevenueStreamsOutput(
            h2_sales_revenue_usd_per_year=h2_revenue,
            electricity_sales_revenue_usd_per_year=electricity_revenue,
            heat_recovery_revenue_usd_per_year=heat_revenue,
            oxygen_byproduct_revenue_usd_per_year=oxygen_revenue,
            total_revenue_usd_per_year=total_revenue,
        )


    # ========== FINANCIAL METRICS ==========

    @classmethod
    def _calculate_financial_metrics(
        cls,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        gp,
        tech_specs,
    ) -> FinancialMetricsOutput:
        """Calculate key financial metrics with inflation and discounting."""
        inv = capex.total_capex_after_subsidy_usd
        annual_revenue = revenue.total_revenue_usd_per_year
        annual_opex = opex.total_opex_usd_per_year
        annual_ebitda = annual_revenue - annual_opex

        discount = gp.discount_rate_percent / 100
        life = gp.project_lifetime_years
        inflation = gp.inflation_percent / 100

        # Build cash flows with inflation
        cash_flows = [-inv]
        for yr in range(1, life + 1):
            # Inflate EBITDA for future years
            cf = annual_ebitda * ((1 + inflation) ** (yr - 1))
            cash_flows.append(cf)

        # Calculate NPV and IRR
        npv = cls._calculate_npv(cash_flows, discount)
        irr = cls._calculate_irr(cash_flows) * 100

        # Payback period (simple, without discounting)
        payback = cls._calculate_payback_period(inv, annual_ebitda) if annual_ebitda > 0 else float("inf")

        # LCOE and LCOH
        annual_electricity = 365 * tech_specs.peak_sun_hours_per_day * 1  # Simplified
        lcoe = cls._calculate_lcoe(inv, annual_opex, annual_electricity, discount, life)
        
        annual_h2 = annual_ebitda / gp.h2_price_usd_per_kg if gp.h2_price_usd_per_kg > 0 else 0
        lcoh = cls._calculate_lcoh(inv, annual_opex, annual_h2, discount, life)

        return FinancialMetricsOutput(
            lcoe_usd_per_kwh=lcoe,
            lcoh_usd_per_kg=lcoh,
            irr_percent=irr,
            npv_usd=npv,
            payback_period_years=payback,
            ebitda_usd_per_year=annual_ebitda,
        )


    @staticmethod
    def _calculate_npv(cash_flows: List[float], discount_rate: float) -> float:
        """Calculate NPV given cash flows and discount rate."""
        return sum(cf / ((1 + discount_rate) ** t) for t, cf in enumerate(cash_flows))

    @staticmethod
    def _calculate_irr(cash_flows: List[float], guess: float = 0.1, iterations: int = 1000) -> float:
        """Calculate IRR using Newton-Raphson method."""
        rate = guess
        for _ in range(iterations):
            npv = sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cash_flows))
            d_npv = sum(-t * cf / ((1 + rate) ** (t + 1)) for t, cf in enumerate(cash_flows))
            if abs(d_npv) < 1e-6:
                break
            rate -= npv / d_npv
        return max(-0.99, rate)

    @staticmethod
    def _calculate_payback_period(investment: float, annual_cash_flow: float) -> float:
        """Simple payback period calculation."""
        return investment / annual_cash_flow if annual_cash_flow > 0 else float("inf")

    @staticmethod
    def _calculate_lcoe(
        investment: float,
        annual_opex: float,
        annual_energy_kwh: float,
        discount_rate: float,
        project_life: int,
    ) -> float:
        """Levelized Cost of Energy."""
        if annual_energy_kwh <= 0:
            return 0
        dr = discount_rate
        if dr > 0:
            annuity = dr * (1 + dr) ** project_life / ((1 + dr) ** project_life - 1)
        else:
            annuity = 1 / project_life
        return (investment * annuity + annual_opex) / annual_energy_kwh

    @staticmethod
    def _calculate_lcoh(
        investment: float,
        annual_opex: float,
        annual_h2_kg: float,
        discount_rate: float,
        project_life: int,
    ) -> float:
        """Levelized Cost of Hydrogen."""
        if annual_h2_kg <= 0:
            return 0
        dr = discount_rate
        if dr > 0:
            annuity = dr * (1 + dr) ** project_life / ((1 + dr) ** project_life - 1)
        else:
            annuity = 1 / project_life
        return (investment * annuity + annual_opex) / annual_h2_kg


    # ========== MONTHLY DATA FOR CHARTING ==========

    @classmethod
    def _calculate_monthly_data(
        cls,
        sizing: SizingOutput,
        revenue: RevenueStreamsOutput,
        opex: OpexBreakdownOutput,
        gp,
    ) -> List[MonthlyDataPoint]:
        """Generate 12 months of revenue vs OPEX data for charting."""
        data = []

        # Monthly values (assume uniform distribution)
        monthly_h2_revenue = revenue.h2_sales_revenue_usd_per_year / 12
        monthly_electricity_revenue = revenue.electricity_sales_revenue_usd_per_year / 12
        monthly_heat_revenue = revenue.heat_recovery_revenue_usd_per_year / 12
        monthly_o2_revenue = revenue.oxygen_byproduct_revenue_usd_per_year / 12
        monthly_opex_base = opex.total_opex_usd_per_year / 12

        for month in range(1, 13):
            # Apply seasonal variation if needed (simplified: use uniform)
            monthly_total_revenue = (
                monthly_h2_revenue
                + monthly_electricity_revenue
                + monthly_heat_revenue
                + monthly_o2_revenue
            )

            # OPEX with inflation applied to current month
            inflation_factor = (1 + gp.inflation_percent / 100) ** ((month - 1) / 12)
            monthly_opex = monthly_opex_base * inflation_factor

            monthly_ebitda = monthly_total_revenue - monthly_opex

            data.append(
                MonthlyDataPoint(
                    month=month,
                    h2_revenue=monthly_h2_revenue,
                    electricity_revenue=monthly_electricity_revenue,
                    heat_revenue=monthly_heat_revenue,
                    oxygen_revenue=monthly_o2_revenue,
                    total_revenue=monthly_total_revenue,
                    total_opex=monthly_opex,
                    ebitda=monthly_ebitda,
                )
            )

        return data

    @staticmethod
    def _aggregate_monthly_data(site_outputs: List[SingleSiteOutput]) -> List[MonthlyDataPoint]:
        """Aggregate monthly data across multiple sites."""
        aggregated = {}
        for month in range(1, 13):
            h2_rev = sum(s.monthly_data[month - 1].h2_revenue for s in site_outputs)
            elec_rev = sum(s.monthly_data[month - 1].electricity_revenue for s in site_outputs)
            heat_rev = sum(s.monthly_data[month - 1].heat_revenue for s in site_outputs)
            o2_rev = sum(s.monthly_data[month - 1].oxygen_revenue for s in site_outputs)
            total_rev = sum(s.monthly_data[month - 1].total_revenue for s in site_outputs)
            opex = sum(s.monthly_data[month - 1].total_opex for s in site_outputs)
            ebitda = sum(s.monthly_data[month - 1].ebitda for s in site_outputs)

            aggregated[month] = MonthlyDataPoint(
                month=month,
                h2_revenue=h2_rev,
                electricity_revenue=elec_rev,
                heat_revenue=heat_rev,
                oxygen_revenue=o2_rev,
                total_revenue=total_rev,
                total_opex=opex,
                ebitda=ebitda,
            )

        return [aggregated[m] for m in range(1, 13)]

    # ========== SENSITIVITY ANALYSIS ==========

    @classmethod
    def _calculate_sensitivity(
        cls,
        sizing: SizingOutput,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        gp,
        tech_specs,
    ) -> List[SensitivityScenario]:
        """Generate sensitivity scenarios for key parameters."""
        scenarios = []

        # Base case
        base_fin = cls._calculate_financial_metrics(capex, opex, revenue, gp, tech_specs)
        scenarios.append(SensitivityScenario(description="Base Case", financial_metrics=base_fin))

        # Discount rate ±10%
        for factor in [0.9, 1.1]:
            gp_mod = gp.model_copy(
                update={"discount_rate_percent": gp.discount_rate_percent * factor}
            )
            fin = cls._calculate_financial_metrics(capex, opex, revenue, gp_mod, tech_specs)
            scenarios.append(
                SensitivityScenario(
                    description=f"Discount Rate {int((factor - 1) * 100):+d}%",
                    financial_metrics=fin,
                )
            )

        # H2 price ±20%
        for factor in [0.8, 1.2]:
            gp_mod = gp.model_copy(update={"h2_price_usd_per_kg": gp.h2_price_usd_per_kg * factor})
            revenue_mod = cls._calculate_revenue(sizing, gp_mod, tech_specs)
            fin = cls._calculate_financial_metrics(capex, opex, revenue_mod, gp, tech_specs)
            scenarios.append(
                SensitivityScenario(
                    description=f"H2 Price {int((factor - 1) * 100):+d}%",
                    financial_metrics=fin,
                )
            )

        # CAPEX ±15%
        for factor in [0.85, 1.15]:
            capex_mod = CapexBreakdownOutput(
                pv_capex_usd=capex.pv_capex_usd * factor,
                battery_capex_usd=capex.battery_capex_usd * factor,
                electrolyzer_capex_usd=capex.electrolyzer_capex_usd * factor,
                h2_storage_capex_usd=capex.h2_storage_capex_usd * factor,
                fuel_cell_capex_usd=capex.fuel_cell_capex_usd * factor,
                balance_of_plant_capex_usd=capex.balance_of_plant_capex_usd * factor,
                total_capex_before_subsidy_usd=capex.total_capex_before_subsidy_usd * factor,
                subsidy_usd=capex.subsidy_usd * factor,
                total_capex_after_subsidy_usd=capex.total_capex_after_subsidy_usd * factor,
            )
            opex_mod = cls._calculate_opex(sizing, capex_mod)
            fin = cls._calculate_financial_metrics(capex_mod, opex_mod, revenue, gp, tech_specs)
            scenarios.append(
                SensitivityScenario(
                    description=f"CAPEX {int((factor - 1) * 100):+d}%",
                    financial_metrics=fin,
                )
            )

        return scenarios
