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
from typing import List, Optional

import importlib
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
    HourlySnapshot,
    OptimizationResult,
)


class HydrogenCalculator:
    """Load-centric calculation engine for HydrogenX.
    
    All component sizing is derived from:
    - daily_load_kw: facility's average daily load
    - battery_autonomy_hours: hours of battery-only operation
    - hydrogen_autonomy_hours: hours of H2 fuel cell operation
    """

    @classmethod
    def build_single_site_input(cls, payload: dict) -> SingleSiteInput:
        """Normalize frontend payload into SingleSiteInput."""
        normalized = {}

        if "site_name" in payload:
            normalized["site_name"] = payload["site_name"]
        if "daily_load_kw" in payload:
            normalized["daily_load_kw"] = payload["daily_load_kw"]
        if "battery_autonomy_hours" in payload:
            normalized["battery_autonomy_hours"] = payload["battery_autonomy_hours"]
        if "hydrogen_autonomy_hours" in payload:
            normalized["hydrogen_autonomy_hours"] = payload["hydrogen_autonomy_hours"]
        if "monthly_ghi" in payload:
            normalized["monthly_ghi"] = payload["monthly_ghi"]

        # load_autonomy block
        la = payload.get("load_autonomy", {}) or {}
        normalized_la = {}
        for key in ["daily_load_kwh", "daily_load_kw", "site_load_kw", "battery_autonomy_hours", "hydrogen_autonomy_hours", "electrolyzer_charge_window_hours"]:
            if key in la:
                normalized_la[key] = la[key]
        if normalized_la:
            normalized["load_autonomy"] = normalized_la

        # sizing_safety_factors alias
        ss = payload.get("sizing_safeties", {}) or {}
        if ss:
            normalized_ss = {}
            if "oversize_factor_pv" in ss:
                normalized_ss["pv_oversizing_factor"] = ss["oversize_factor_pv"]
            if "safety_margin" in ss:
                normalized_ss["safety_margin_general"] = ss["safety_margin"]
            if normalized_ss:
                normalized["sizing_safety_factors"] = normalized_ss

        # tech specs (directly accepted)
        if "tech_specs" in payload and payload["tech_specs"] is not None:
            normalized["tech_specs"] = payload["tech_specs"]

        # global params (directly accepted)
        if "global_params" in payload and payload["global_params"] is not None:
            normalized["global_params"] = payload["global_params"]

        # cost parameters alias mapping
        costs = payload.get("costs", {}) or {}
        if costs:
            normalized_cp = {}
            if "solar_pv_cost_per_kw" in costs:
                normalized_cp["solar_pv_cost_usd_per_kwp"] = costs["solar_pv_cost_per_kw"]
            if "battery_cost_per_kwh" in costs:
                normalized_cp["battery_cost_usd_per_kwh"] = costs["battery_cost_per_kwh"]
            if "fuel_cell_cost_per_kw" in costs:
                normalized_cp["fuel_cell_cost_usd_per_kw"] = costs["fuel_cell_cost_per_kw"]
            if "electrolyzer_cost_per_kw" in costs:
                normalized_cp["electrolyzer_cost_usd_per_kw"] = costs["electrolyzer_cost_per_kw"]
            if "oxygen_production_ratio" in costs:
                normalized_cp["oxygen_production_ratio_kg_per_kg"] = costs["oxygen_production_ratio"]
            if "oxygen_price_per_kg" in costs:
                normalized_cp["oxygen_price_usd_per_kg"] = costs["oxygen_price_per_kg"]
            if normalized_cp:
                normalized["cost_parameters"] = normalized_cp

        # opex_params and market_params -> financial assumptions
        fa = payload.get("opex_params", {}) or {}
        mp = payload.get("market_params", {}) or {}
        if fa or mp:
            normalized_fa = {}
            if "opex_rate_pv_battery_percent" in fa:
                normalized_fa["opex_rate_pv_battery_percent"] = fa["opex_rate_pv_battery_percent"]
            if "opex_rate_electrolyzer_fuel_cell_percent" in fa:
                normalized_fa["opex_rate_electrolyzer_fc_percent"] = fa["opex_rate_electrolyzer_fuel_cell_percent"]
            if "diesel_lcoe_usd_per_kwh" in mp:
                normalized_fa["diesel_lcoe_usd_per_kwh"] = mp["diesel_lcoe_usd_per_kwh"]
            if "units_deployed" in mp:
                normalized_fa["units_deployed"] = mp["units_deployed"]
            # Some market params may be in top-level map
            if normalized_fa:
                normalized["financial_assumptions"] = normalized_fa

        # Build SingleSiteInput confidently with defaults for missing sections
        return SingleSiteInput(**normalized)

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
        # Map frontend fields to internal structure
        cls._map_frontend_fields(input_data)
        
        la = input_data.load_autonomy
        ec = input_data.efficiencies_constants
        sf = input_data.sizing_safety_factors
        fa = input_data.financial_assumptions
        cp = input_data.cost_parameters

        # Determine the average site load in kW.
        # Priority: top-level daily_load_kw -> nested load_autonomy.site_load_kw -> nested load_autonomy.daily_load_kw -> derived from daily_load_kwh.
        if la.site_load_kw is not None:
            daily_load_kw = la.site_load_kw
        elif getattr(la, "daily_load_kw", None) is not None:
            daily_load_kw = la.daily_load_kw
        else:
            daily_load_kw = la.daily_load_kwh / 24

        # === STEP 1: SIZING ===
        sizing = cls._calculate_sizing_from_load(
            daily_load_kw=daily_load_kw,
            load_autonomy=la,
            efficiencies_constants=ec,
            sizing_safety_factors=sf,
            cost_parameters=cp,
            financial_assumptions=fa,
            monthly_ghi=input_data.monthly_ghi,
        )

        # === STEP 2: CAPEX ===
        capex = cls._calculate_capex(sizing, cp, fa)

        # === STEP 3: OPEX ===
        opex = cls._calculate_opex(sizing, capex, fa)

        # === STEP 4: REVENUE ===
        revenue = cls._calculate_revenue(sizing, ec, fa, cp)

        # === STEP 5: FINANCIAL METRICS ===
        financial = cls._calculate_financial_metrics(capex, opex, revenue, fa, ec, sizing)

        # === STEP 6: MONTHLY DATA ===
        monthly = cls._calculate_monthly_data(sizing, revenue, opex, fa)

        # === STEP 7: SENSITIVITY (optional) ===
        sensitivity = cls._calculate_sensitivity(input_data, sizing, capex, opex, revenue, fa, ec)

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
    def _map_frontend_fields(cls, input_data: SingleSiteInput) -> None:
        """Map frontend top-level fields to internal nested structure."""
        # Map load autonomy
        if input_data.daily_load_kw is not None:
            input_data.load_autonomy.site_load_kw = input_data.daily_load_kw

        # Accept either nested load_autonomy.daily_load_kw or nested load_autonomy.site_load_kw
        if getattr(input_data.load_autonomy, "daily_load_kw", None) is not None and input_data.load_autonomy.site_load_kw is None:
            input_data.load_autonomy.site_load_kw = input_data.load_autonomy.daily_load_kw

        if input_data.battery_autonomy_hours is not None:
            input_data.load_autonomy.battery_autonomy_hours = input_data.battery_autonomy_hours
        if input_data.hydrogen_autonomy_hours is not None:
            input_data.load_autonomy.hydrogen_autonomy_hours = input_data.hydrogen_autonomy_hours
        
        # Map tech specs
        if input_data.tech_specs is not None:
            ts = input_data.tech_specs
            input_data.efficiencies_constants.battery_dod_percent = ts.battery_usable_ratio * 100
            input_data.efficiencies_constants.battery_efficiency_percent = ts.battery_efficiency_percent
            input_data.efficiencies_constants.fuel_cell_efficiency_percent = ts.fuel_cell_efficiency_percent
            input_data.efficiencies_constants.electrolyzer_efficiency_percent = ts.electrolyzer_efficiency_percent
            input_data.efficiencies_constants.pv_efficiency_factor = ts.pv_performance_ratio
            input_data.efficiencies_constants.battery_cycle_life_cycles = ts.battery_cycle_life_cycles
            input_data.efficiencies_constants.battery_end_of_life_capacity_percent = ts.battery_end_of_life_capacity_percent
            # Set PSH to the provided value for both months
            input_data.efficiencies_constants.jan_average_psh = ts.peak_sun_hours_per_day
            input_data.efficiencies_constants.august_average_psh = ts.peak_sun_hours_per_day

        # Apply optional monthly GHI overrides when available
        if input_data.monthly_ghi is not None:
            ghi = input_data.monthly_ghi
            if len(ghi) != 12:
                raise ValueError("monthly_ghi must contain 12 monthly values")
            input_data.efficiencies_constants.jan_average_psh = ghi[0]
            input_data.efficiencies_constants.august_average_psh = ghi[7]

        # Map global params
        if input_data.global_params is not None:
            gp = input_data.global_params
            input_data.financial_assumptions.discount_rate_percent = gp.discount_rate_percent
            input_data.financial_assumptions.opex_inflation_percent = gp.inflation_percent
            input_data.financial_assumptions.capex_subsidy_percent = gp.subsidy_percent
            input_data.financial_assumptions.eaas_price_usd_per_kwh = gp.eaas_price_usd_per_kwh
            input_data.financial_assumptions.system_lifetime_years = gp.project_lifetime_years
            input_data.financial_assumptions.operation_days_per_year = gp.operation_days_per_year

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
        load_autonomy,
        efficiencies_constants,
        sizing_safety_factors,
        cost_parameters,
        financial_assumptions,
        monthly_ghi: Optional[List[float]] = None,
    ) -> SizingOutput:
        """Calculate component sizing based on daily load and autonomy requirements."""

        daily_consumption_kwh = daily_load_kw * 24

        # === BATTERY ===
        battery_dod = efficiencies_constants.battery_dod_percent / 100
        battery_eff = efficiencies_constants.battery_efficiency_percent / 100
        battery_usable_needed = daily_load_kw * load_autonomy.battery_autonomy_hours
        battery_gross_capacity = battery_usable_needed / (battery_dod * battery_eff)
        battery_power_rating = daily_load_kw * sizing_safety_factors.safety_margin_general

        # === HYDROGEN & FUEL CELL ===
        h2_lhv = efficiencies_constants.hydrogen_lhv_kwh_per_kg
        fc_eff = efficiencies_constants.fuel_cell_efficiency_percent / 100
        energy_for_h2 = daily_load_kw * load_autonomy.hydrogen_autonomy_hours
        h2_daily_kg = energy_for_h2 / (fc_eff * h2_lhv)
        h2_storage_capacity = h2_daily_kg * (load_autonomy.hydrogen_autonomy_hours / 24)

        fuel_cell_power = daily_load_kw * sizing_safety_factors.safety_margin_general

        # === ELECTROLYZER ===
        ely_eff = efficiencies_constants.electrolyzer_efficiency_percent / 100
        charge_window = load_autonomy.electrolyzer_charge_window_hours
        ely_daily_kwh = h2_daily_kg * (h2_lhv / ely_eff)
        electrolyzer_power = max(1.0, ely_daily_kwh / charge_window)

        # === PV SIZING ===
        if monthly_ghi is not None and len(monthly_ghi) == 12:
            avg_psh = sum(monthly_ghi) / 12.0
        else:
            avg_psh = (efficiencies_constants.jan_average_psh + efficiencies_constants.august_average_psh) / 2.0

        battery_loss_kwh = battery_usable_needed * (1 / battery_eff - 1)
        total_energy_needed = (
            daily_consumption_kwh +
            battery_loss_kwh +
            ely_daily_kwh
        ) * sizing_safety_factors.safety_margin_general

        pv_eff_factor = efficiencies_constants.pv_efficiency_factor
        pv_capacity_kwp = total_energy_needed / (avg_psh * pv_eff_factor)
        pv_capacity_kwp *= sizing_safety_factors.pv_oversizing_factor

        pv_area_m2 = pv_capacity_kwp * 6.0

        battery_cycles, battery_capacity_factor, battery_eol_capacity_factor = cls._calculate_battery_degradation(
            efficiencies_constants, financial_assumptions
        )

        return SizingOutput(
            daily_consumption_kwh=daily_consumption_kwh,
            battery_capacity_kwh=battery_gross_capacity,
            battery_power_rating_kw=battery_power_rating,
            battery_usable_kwh=battery_usable_needed,
            h2_daily_production_kg=h2_daily_kg,
            h2_storage_capacity_kg=h2_storage_capacity,
            electrolyzer_capacity_kw=electrolyzer_power,
            fuel_cell_capacity_kw=fuel_cell_power,
            pv_capacity_kwp=pv_capacity_kwp,
            pv_area_m2=pv_area_m2,
            battery_cumulative_cycles=battery_cycles,
            battery_capacity_factor=battery_capacity_factor,
            battery_eol_capacity_factor=battery_eol_capacity_factor,
        )

    @classmethod
    def _calculate_battery_degradation(cls, efficiencies_constants, financial_assumptions) -> tuple[float, float, float]:
        """Estimate battery fade based on cycle life assumptions."""
        cycles_per_year = financial_assumptions.operation_days_per_year
        total_cycles = cycles_per_year * financial_assumptions.system_lifetime_years

        eol_capacity_fraction = (
            efficiencies_constants.battery_end_of_life_capacity_percent / 100
            if hasattr(efficiencies_constants, 'battery_end_of_life_capacity_percent')
            else 0.8
        )
        fade_per_cycle = max(0.0, (1 - eol_capacity_fraction) / efficiencies_constants.battery_cycle_life_cycles)
        end_of_life_factor = max(eol_capacity_fraction, 1 - fade_per_cycle * total_cycles)
        average_factor = max(eol_capacity_fraction, (1 + end_of_life_factor) / 2)

        return total_cycles, average_factor, end_of_life_factor

    @classmethod
    def _calculate_capex(cls, sizing: SizingOutput, cost_parameters, financial_assumptions) -> CapexBreakdownOutput:
        """Exact match to Excel CAPEX (no placeholder H2 storage cost)."""

        pv_capex = sizing.pv_capacity_kwp * cost_parameters.solar_pv_cost_usd_per_kwp
        battery_capex = sizing.battery_capacity_kwh * cost_parameters.battery_cost_usd_per_kwh
        electrolyzer_capex = sizing.electrolyzer_capacity_kw * cost_parameters.electrolyzer_cost_usd_per_kw
        fuel_cell_capex = sizing.fuel_cell_capacity_kw * cost_parameters.fuel_cell_cost_usd_per_kw

        h2_storage_capex = 0.0
        component_sum = pv_capex + battery_capex + electrolyzer_capex + fuel_cell_capex + h2_storage_capex
        bop_capex = 0.0

        total_capex = component_sum
        subsidy = total_capex * (financial_assumptions.capex_subsidy_percent / 100)
        capex_after_subsidy = total_capex - subsidy

        return CapexBreakdownOutput(
            pv_capex_usd=pv_capex,
            battery_capex_usd=battery_capex,
            electrolyzer_capex_usd=electrolyzer_capex,
            h2_storage_capex_usd=h2_storage_capex,
            fuel_cell_capex_usd=fuel_cell_capex,
            balance_of_plant_capex_usd=bop_capex,
            total_capex_before_subsidy_usd=total_capex,
            subsidy_usd=subsidy,
            total_capex_after_subsidy_usd=capex_after_subsidy,
        )

    @classmethod
    def _calculate_opex(cls, sizing: SizingOutput, capex: CapexBreakdownOutput, financial_assumptions) -> OpexBreakdownOutput:
        """Exact Excel OPEX groups (2% PV+Batt, 3% Ely+FC)."""

        group_a = (capex.pv_capex_usd + capex.battery_capex_usd) * (financial_assumptions.opex_rate_pv_battery_percent / 100)
        group_b = (capex.electrolyzer_capex_usd + capex.fuel_cell_capex_usd) * (financial_assumptions.opex_rate_electrolyzer_fc_percent / 100)
        total_opex = group_a + group_b

        return OpexBreakdownOutput(
            pv_battery_opex_usd_per_year=group_a,
            electrolyzer_fc_opex_usd_per_year=group_b,
            h2_storage_bop_opex_usd_per_year=0.0,
            total_opex_usd_per_year=total_opex,
        )


    # ========== REVENUE CALCULATIONS ==========
    @classmethod
    def _calculate_revenue(cls, sizing: SizingOutput, efficiencies_constants, financial_assumptions, cost_parameters) -> RevenueStreamsOutput:
        # 1. EaaS Revenue (The core electricity sales)
        # Based on actual 8kW load served
        annual_load_kwh = sizing.daily_consumption_kwh * 365
        electricity_revenue = annual_load_kwh * financial_assumptions.eaas_price_usd_per_kwh

        # 2. Oxygen Revenue (9kg of O2 per 1kg of H2)
        h2_annual_kg = sizing.h2_daily_production_kg * 365
        o2_annual_kg = h2_annual_kg * cost_parameters.oxygen_production_ratio_kg_per_kg
        oxygen_revenue = o2_annual_kg * cost_parameters.oxygen_price_usd_per_kg

        # 3. Heat Recovery (Thermal recovery from the electrolyzer/FC)
        # Assuming you sell the recovered heat at a specific rate
        heat_price = getattr(cost_parameters, 'heat_price_usd_per_kwh', 0.05) 
        heat_revenue = h2_annual_kg * efficiencies_constants.hydrogen_lhv_kwh_per_kg * 0.20 * heat_price # Example 20% recovery

        # 4. Total
        total_revenue = electricity_revenue + oxygen_revenue + heat_revenue

        return RevenueStreamsOutput(
            h2_sales_revenue_usd_per_year=0.0, # Kept separate if not selling H2 directly
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
        financial_assumptions,
        efficiencies_constants,
        sizing: SizingOutput,
    ) -> FinancialMetricsOutput:
        """Calculate key financial metrics with inflation and discounting."""
        # Use pre-subsidy CAPEX for levelized costs and discounting to align with typical Excel models
        inv_pre_subsidy = capex.total_capex_before_subsidy_usd
        # Use the EaaS electricity revenue stream as the primary cashflow driver (matches Excel model)
        annual_revenue = revenue.electricity_sales_revenue_usd_per_year
        annual_opex = opex.total_opex_usd_per_year
        annual_ebitda = annual_revenue - annual_opex

        discount = financial_assumptions.discount_rate_percent / 100
        life = int(financial_assumptions.system_lifetime_years)
        inflation = financial_assumptions.opex_inflation_percent / 100
        revenue_growth = financial_assumptions.revenue_growth_percent / 100
        contract_years = int(financial_assumptions.eaas_contract_years)

        # Build cash flows (year 0 = -investment; years 1..contract_years = EBITDA with growth + inflation)
        cash_flows = [-inv_pre_subsidy]
        for yr in range(1, contract_years + 1):
            rev = annual_revenue * ((1 + revenue_growth) ** (yr - 1))
            opex = annual_opex * ((1 + inflation) ** (yr - 1))
            cash_flows.append(rev - opex)

        # Calculate NPV and IRR based on the contract cash flows
        npv = cls._calculate_npv(cash_flows, discount)
        irr = cls._calculate_irr(cash_flows) * 100

        # Payback period (simple, without discounting) using base EBITDA
        payback = cls._calculate_payback_period(inv_pre_subsidy, annual_ebitda) if annual_ebitda > 0 else float("inf")

        # Discounted revenue/opex/energy for reporting and LCOE
        discounted_revenue = 0.0
        for yr in range(1, contract_years + 1):
            rev = annual_revenue * ((1 + revenue_growth) ** (yr - 1))
            discounted_revenue += rev / ((1 + discount) ** yr)

        discounted_opex = 0.0
        for yr in range(1, life + 1):
            opex = annual_opex * ((1 + inflation) ** (yr - 1))
            discounted_opex += opex / ((1 + discount) ** yr)

        discounted_energy = 0.0
        annual_energy_kwh = sizing.daily_consumption_kwh * 365
        eol_factor = getattr(sizing, 'battery_eol_capacity_factor', 1.0)
        for yr in range(1, life + 1):
            year_factor = 1.0
            if life > 1:
                year_factor = max(eol_factor, 1.0 - (1.0 - eol_factor) * ((yr - 1) / (life - 1)))
            discounted_energy += annual_energy_kwh * year_factor / ((1 + discount) ** yr)

        total_discounted_cost = inv_pre_subsidy + discounted_opex

        # LCOE and LCOH based on discounted totals and battery degradation
        lcoe = total_discounted_cost / discounted_energy if discounted_energy > 0 else 0
        annual_h2_kg = sizing.h2_daily_production_kg * 365 * getattr(sizing, 'battery_capacity_factor', 1.0)
        lcoh = cls._calculate_lcoh(inv_pre_subsidy, annual_opex, annual_h2_kg, discount, life)

        return FinancialMetricsOutput(
            lcoe_usd_per_kwh=lcoe,
            lcoh_usd_per_kg=lcoh,
            irr_percent=irr,
            npv_usd=npv,
            payback_period_years=payback,
            ebitda_usd_per_year=annual_ebitda,
            discounted_revenue_usd=discounted_revenue,
            discounted_opex_usd=discounted_opex,
            discounted_energy_kwh=discounted_energy,
            total_discounted_cost_usd=total_discounted_cost,
            cash_flow_usd=cash_flows,
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
    def _calculate_lcoe( investment: float,
        annual_opex: float,
        annual_energy_kwh: float,
        discount_rate: float,
        project_life: int, ) -> float:
        """Standard DCF LCOE to match Excel."""
        total_costs_npv = investment
        total_energy_discounted = 0
        for year in range(1, project_life + 1):
            total_costs_npv += annual_opex / ((1 + discount_rate) ** year)
            total_energy_discounted += annual_energy_kwh / ((1 + discount_rate) ** year)
        return total_costs_npv / total_energy_discounted if total_energy_discounted > 0 else 0
    
    # @staticmethod
    # def _calculate_lcoe(
    #     investment: float,
    #     annual_opex: float,
    #     annual_energy_kwh: float,
    #     discount_rate: float,
    #     project_life: int,
    # ) -> float:
    #     """Levelized Cost of Energy."""
    #     if annual_energy_kwh <= 0:
    #         return 0
    #     dr = discount_rate
    #     if dr > 0:
    #         annuity = dr * (1 + dr) ** project_life / ((1 + dr) ** project_life - 1)
    #     else:
    #         annuity = 1 / project_life
    #     return (investment * annuity + annual_opex) / annual_energy_kwh

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
        financial_assumptions,
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
            inflation_factor = (1 + financial_assumptions.opex_inflation_percent / 100) ** ((month - 1) / 12)
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
        input_data: SingleSiteInput,
        sizing: SizingOutput,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        financial_assumptions,
        efficiencies_constants,
    ) -> List[SensitivityScenario]:
        """Generate sensitivity scenarios for key parameters."""
        scenarios = []
        base = {
            'cost_parameters': input_data.cost_parameters,
            'financial_assumptions': input_data.financial_assumptions,
        }

        def build_scenario(name: str, description: str, cost_delta: float = 0.0, discount_delta: float = 0.0, eaas_delta: float = 0.0, battery_cost_delta: float = 0.0, fuel_cell_cost_delta: float = 0.0):
            modified = input_data.model_copy(deep=True)
            if cost_delta:
                modified.cost_parameters = modified.cost_parameters.model_copy(deep=True)
                modified.cost_parameters.solar_pv_cost_usd_per_kwp *= 1 + cost_delta
                modified.cost_parameters.battery_cost_usd_per_kwh *= 1 + cost_delta
                modified.cost_parameters.electrolyzer_cost_usd_per_kw *= 1 + cost_delta
                modified.cost_parameters.fuel_cell_cost_usd_per_kw *= 1 + cost_delta
            if battery_cost_delta:
                modified.cost_parameters = modified.cost_parameters.model_copy(deep=True)
                modified.cost_parameters.battery_cost_usd_per_kwh *= 1 + battery_cost_delta
            if fuel_cell_cost_delta:
                modified.cost_parameters = modified.cost_parameters.model_copy(deep=True)
                modified.cost_parameters.fuel_cell_cost_usd_per_kw *= 1 + fuel_cell_cost_delta
            if discount_delta:
                modified.financial_assumptions = modified.financial_assumptions.model_copy(deep=True)
                modified.financial_assumptions.discount_rate_percent = max(0.0, modified.financial_assumptions.discount_rate_percent + discount_delta)
            if eaas_delta:
                modified.financial_assumptions = modified.financial_assumptions.model_copy(deep=True)
                modified.financial_assumptions.eaas_price_usd_per_kwh *= 1 + eaas_delta

            cls._map_frontend_fields(modified)
            daily_load_kw = modified.load_autonomy.site_load_kw or modified.load_autonomy.daily_load_kw or modified.load_autonomy.daily_load_kwh / 24
            scenario_sizing = cls._calculate_sizing_from_load(
                daily_load_kw=daily_load_kw,
                load_autonomy=modified.load_autonomy,
                efficiencies_constants=modified.efficiencies_constants,
                sizing_safety_factors=modified.sizing_safety_factors,
                cost_parameters=modified.cost_parameters,
                financial_assumptions=modified.financial_assumptions,
                monthly_ghi=modified.monthly_ghi,
            )
            scenario_capex = cls._calculate_capex(scenario_sizing, modified.cost_parameters, modified.financial_assumptions)
            scenario_opex = cls._calculate_opex(scenario_sizing, scenario_capex, modified.financial_assumptions)
            scenario_revenue = cls._calculate_revenue(scenario_sizing, modified.efficiencies_constants, modified.financial_assumptions, modified.cost_parameters)
            scenario_financials = cls._calculate_financial_metrics(
                scenario_capex,
                scenario_opex,
                scenario_revenue,
                modified.financial_assumptions,
                modified.efficiencies_constants,
                scenario_sizing,
            )
            return SensitivityScenario(
                name=name,
                description=description,
                financial_metrics=scenario_financials,
            )

        scenarios.append(build_scenario('Base Case', 'Original assumptions'))
        scenarios.append(build_scenario('+10% CAPEX', 'Higher capital costs', cost_delta=0.10))
        scenarios.append(build_scenario('-10% CAPEX', 'Lower capital costs', cost_delta=-0.10))
        scenarios.append(build_scenario('+2% Discount Rate', 'Higher finance cost', discount_delta=2.0))
        scenarios.append(build_scenario('-2% Discount Rate', 'Lower finance cost', discount_delta=-2.0))
        scenarios.append(build_scenario('+15% EaaS Price', 'Higher electricity revenue', eaas_delta=0.15))
        scenarios.append(build_scenario('-15% EaaS Price', 'Lower electricity revenue', eaas_delta=-0.15))
        scenarios.append(build_scenario('+10% Battery Cost', 'Higher battery CAPEX', battery_cost_delta=0.10))
        scenarios.append(build_scenario('-10% Fuel Cell Cost', 'Lower fuel cell CAPEX', fuel_cell_cost_delta=-0.10))

        return scenarios

    @classmethod
    def estimate_location_monthly_psh(cls, latitude: float, longitude: float) -> List[float]:
        """Estimate monthly average PSH using pvlib when available, otherwise fallback."""
        try:
            pd = importlib.import_module('pandas')
            pvlib = importlib.import_module('pvlib')
            Location = pvlib.location.Location

            location = Location(latitude, longitude)
            times = pd.date_range('2020-01-01', '2020-12-31 23:00', freq='H', tz='UTC')
            clearsky = location.get_clearsky(times)
            monthly_sum = clearsky['ghi'].resample('M').sum() / 1000.0
            monthly_days = clearsky['ghi'].resample('M').count() / 24.0
            return [round(float(monthly_sum.loc[idx] / monthly_days.loc[idx]), 2) for idx in monthly_sum.index]
        except Exception:
            return cls._estimate_monthly_psh_fallback(latitude, longitude)

    @classmethod
    def _estimate_monthly_psh_fallback(cls, latitude: float, longitude: float) -> List[float]:
        """Fallback monthly PSH estimate using latitude-driven seasonality."""
        lat_factor = max(0.5, 1.0 - abs(latitude) / 90.0)
        base = 5.5 * lat_factor
        monthly = []
        for month in range(1, 13):
            seasonal = 0.8 + 0.4 * math.cos(2 * math.pi * (month - 6) / 12)
            monthly.append(round(max(1.0, base * seasonal), 2))
        return monthly

    @classmethod
    def simulate_hourly(cls, input_data: SingleSiteInput, hourly_ghi: List[float]) -> List[HourlySnapshot]:
        """Simulate hourly energy balance and component dispatch for one year."""
        if len(hourly_ghi) != 8760:
            raise ValueError('hourly_ghi must contain 8760 hourly values')

        # Ensure input_data is normalized before running simulation.
        sim_input = input_data.model_copy(deep=True)
        cls._map_frontend_fields(sim_input)

        la = sim_input.load_autonomy
        ec = sim_input.efficiencies_constants
        sizing = cls._calculate_sizing_from_load(
            daily_load_kw=la.site_load_kw or la.daily_load_kw or la.daily_load_kwh / 24,
            load_autonomy=la,
            efficiencies_constants=ec,
            sizing_safety_factors=sim_input.sizing_safety_factors,
            cost_parameters=sim_input.cost_parameters,
            financial_assumptions=sim_input.financial_assumptions,
            monthly_ghi=sim_input.monthly_ghi,
        )

        battery_soc = sizing.battery_usable_kwh * 0.5
        h2_stored = sizing.h2_storage_capacity_kg * 0.5
        max_h2_storage = sizing.h2_storage_capacity_kg
        battery_roundtrip_eff = ec.battery_efficiency_percent / 100
        electrolyzer_eff = ec.electrolyzer_efficiency_percent / 100
        fuel_cell_eff = ec.fuel_cell_efficiency_percent / 100
        hydrogen_lhv = ec.hydrogen_lhv_kwh_per_kg
        snapshots: List[HourlySnapshot] = []

        for hour in range(8760):
            ghi = hourly_ghi[hour]
            pv_production = sizing.pv_capacity_kwp * ghi * ec.pv_efficiency_factor
            load_kwh = sizing.daily_consumption_kwh / 24.0
            net_energy = pv_production - load_kwh

            battery_charge = 0.0
            battery_discharge = 0.0
            electrolyzer_dispatch = 0.0
            fuel_cell_dispatch = 0.0
            h2_produced = 0.0
            h2_consumed = 0.0
            excess_export = 0.0

            if net_energy >= 0:
                available_for_storage = min(net_energy, sizing.battery_usable_kwh - battery_soc)
                battery_charge = available_for_storage * battery_roundtrip_eff
                battery_soc += battery_charge
                surplus = net_energy - available_for_storage

                electrolyzer_dispatch = min(surplus, sizing.electrolyzer_capacity_kw)
                h2_produced = electrolyzer_dispatch * electrolyzer_eff / hydrogen_lhv
                h2_stored = min(max_h2_storage, h2_stored + h2_produced)
                excess_export = max(0.0, surplus - electrolyzer_dispatch)
            else:
                demand = -net_energy
                battery_discharge = min(demand, battery_soc)
                battery_soc -= battery_discharge
                demand -= battery_discharge

                if demand > 0:
                    fuel_cell_dispatch = min(demand, sizing.fuel_cell_capacity_kw)
                    h2_needed = fuel_cell_dispatch / fuel_cell_eff / hydrogen_lhv
                    h2_consumed = min(h2_stored, h2_needed)
                    fuel_cell_dispatch = h2_consumed * fuel_cell_eff * hydrogen_lhv
                    h2_stored -= h2_consumed
                    demand -= fuel_cell_dispatch
                    excess_export = 0.0

            snapshots.append(HourlySnapshot(
                hour=hour,
                pv_production_kwh=round(pv_production, 4),
                load_kwh=round(load_kwh, 4),
                battery_soc_kwh=round(battery_soc, 4),
                battery_charge_kwh=round(battery_charge, 4),
                battery_discharge_kwh=round(battery_discharge, 4),
                h2_produced_kg=round(h2_produced, 6),
                h2_consumed_kg=round(h2_consumed, 6),
                h2_stored_kg=round(h2_stored, 6),
                electrolyzer_dispatch_kwh=round(electrolyzer_dispatch, 4),
                fuel_cell_dispatch_kwh=round(fuel_cell_dispatch, 4),
                excess_export_kwh=round(excess_export, 4),
            ))

        return snapshots

    @classmethod
    def optimize_sizing(cls, input_data: SingleSiteInput) -> OptimizationResult:
        """Find the best battery and hydrogen autonomy pair to minimize LCOE."""
        try:
            scipy_optimize = importlib.import_module('scipy.optimize')
            differential_evolution = scipy_optimize.differential_evolution
        except ModuleNotFoundError as exc:
            raise RuntimeError('scipy is required for optimization. Install scipy and retry.') from exc

        baseline = input_data.model_copy(deep=True)
        cls._map_frontend_fields(baseline)

        def objective(variables):
            battery_hours, hydrogen_hours = variables
            candidate = baseline.model_copy(deep=True)
            candidate.battery_autonomy_hours = float(battery_hours)
            candidate.hydrogen_autonomy_hours = float(hydrogen_hours)
            candidate.load_autonomy.battery_autonomy_hours = float(battery_hours)
            candidate.load_autonomy.hydrogen_autonomy_hours = float(hydrogen_hours)
            cls._map_frontend_fields(candidate)
            daily_load_kw = candidate.load_autonomy.site_load_kw or candidate.load_autonomy.daily_load_kw or candidate.load_autonomy.daily_load_kwh / 24
            sizing = cls._calculate_sizing_from_load(
                daily_load_kw=daily_load_kw,
                load_autonomy=candidate.load_autonomy,
                efficiencies_constants=candidate.efficiencies_constants,
                sizing_safety_factors=candidate.sizing_safety_factors,
                cost_parameters=candidate.cost_parameters,
                financial_assumptions=candidate.financial_assumptions,
                monthly_ghi=candidate.monthly_ghi,
            )
            capex = cls._calculate_capex(sizing, candidate.cost_parameters, candidate.financial_assumptions)
            opex = cls._calculate_opex(sizing, capex, candidate.financial_assumptions)
            revenue = cls._calculate_revenue(sizing, candidate.efficiencies_constants, candidate.financial_assumptions, candidate.cost_parameters)
            metrics = cls._calculate_financial_metrics(capex, opex, revenue, candidate.financial_assumptions, candidate.efficiencies_constants, sizing)
            return metrics.lcoe_usd_per_kwh

        bounds = [(1.0, 24.0), (0.0, 24.0)]
        result = differential_evolution(objective, bounds=bounds, maxiter=15, popsize=10, polish=True)

        best_battery, best_hydrogen = result.x
        best_candidate = baseline.model_copy(deep=True)
        best_candidate.battery_autonomy_hours = float(best_battery)
        best_candidate.hydrogen_autonomy_hours = float(best_hydrogen)
        best_candidate.load_autonomy.battery_autonomy_hours = float(best_battery)
        best_candidate.load_autonomy.hydrogen_autonomy_hours = float(best_hydrogen)
        cls._map_frontend_fields(best_candidate)
        best_sizing = cls._calculate_sizing_from_load(
            daily_load_kw=best_candidate.load_autonomy.site_load_kw or best_candidate.load_autonomy.daily_load_kw or best_candidate.load_autonomy.daily_load_kwh / 24,
            load_autonomy=best_candidate.load_autonomy,
            efficiencies_constants=best_candidate.efficiencies_constants,
            sizing_safety_factors=best_candidate.sizing_safety_factors,
            cost_parameters=best_candidate.cost_parameters,
            financial_assumptions=best_candidate.financial_assumptions,
            monthly_ghi=best_candidate.monthly_ghi,
        )
        best_capex = cls._calculate_capex(best_sizing, best_candidate.cost_parameters, best_candidate.financial_assumptions)
        best_opex = cls._calculate_opex(best_sizing, best_capex, best_candidate.financial_assumptions)
        best_revenue = cls._calculate_revenue(best_sizing, best_candidate.efficiencies_constants, best_candidate.financial_assumptions, best_candidate.cost_parameters)
        best_metrics = cls._calculate_financial_metrics(best_capex, best_opex, best_revenue, best_candidate.financial_assumptions, best_candidate.efficiencies_constants, best_sizing)

        return OptimizationResult(
            optimal_battery_autonomy_hours=float(best_battery),
            optimal_hydrogen_autonomy_hours=float(best_hydrogen),
            optimal_lcoe_usd_per_kwh=best_metrics.lcoe_usd_per_kwh,
            optimal_irr_percent=best_metrics.irr_percent,
            optimal_npv_usd=best_metrics.npv_usd,
            optimal_payback_period_years=best_metrics.payback_period_years,
            optimization_success=bool(result.success),
            optimization_message=result.message,
        )
