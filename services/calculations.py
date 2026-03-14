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
        la = input_data.load_autonomy
        ec = input_data.efficiencies_constants
        sf = input_data.sizing_safety_factors
        fa = input_data.financial_assumptions
        cp = input_data.cost_parameters

        # Use site_load_kwh directly if provided, otherwise convert from daily_load_kwh
        if la.site_load_kwh is not None:
            daily_load_kw = la.site_load_kwh
        else:
            # Convert daily load from kWh/day to kW
            daily_load_kw = la.daily_load_kwh / 24

        # === STEP 1: SIZING ===
        sizing = cls._calculate_sizing_from_load(
            daily_load_kw=daily_load_kw,
            battery_autonomy_hours=la.battery_autonomy_hours,
            hydrogen_autonomy_hours=la.hydrogen_autonomy_hours,
            efficiencies_constants=ec,
            sizing_safety_factors=sf,
            cost_parameters=cp,
            financial_assumptions=fa,
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
        sensitivity = cls._calculate_sensitivity(sizing, capex, opex, revenue, fa, ec)

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
        efficiencies_constants,
        sizing_safety_factors,
        cost_parameters,
        financial_assumptions,
    ) -> SizingOutput:
        """Calculate component sizing based on daily load and autonomy requirements."""

        daily_consumption_kwh = daily_load_kw * 24

        # === BATTERY ===
        battery_dod = efficiencies_constants.battery_dod_percent / 100
        battery_usable_needed = daily_load_kw * battery_autonomy_hours
        battery_gross_capacity = battery_usable_needed / battery_dod
        battery_power_rating = daily_load_kw * sizing_safety_factors.safety_margin_general

        # === HYDROGEN & FUEL CELL ===
        h2_lhv = efficiencies_constants.hydrogen_lhv_kwh_per_kg
        fc_eff = efficiencies_constants.fuel_cell_efficiency_percent / 100
        energy_needed_for_h2 = daily_load_kw * hydrogen_autonomy_hours
        h2_daily_kg = energy_needed_for_h2 / (fc_eff * h2_lhv)

        h2_storage_capacity = h2_daily_kg * (hydrogen_autonomy_hours / 24)

        fuel_cell_power = (daily_load_kw / fc_eff) * sizing_safety_factors.safety_margin_general

        # === ELECTROLYZER ===
        ely_eff = efficiencies_constants.electrolyzer_efficiency_percent / 100
        charge_window = getattr(efficiencies_constants, 'electrolyzer_charge_window_hours', 5)  # default 5h
        ely_daily_kwh = h2_daily_kg * (h2_lhv / ely_eff)
        electrolyzer_power = ely_daily_kwh / charge_window

        # === PV ===
        pv_eff_factor = efficiencies_constants.pv_efficiency_factor
        avg_psh = (efficiencies_constants.jan_average_psh + efficiencies_constants.august_average_psh) / 2

        battery_charging_kwh = daily_consumption_kwh / (efficiencies_constants.battery_efficiency_percent / 100)
        total_pv_energy_needed = (
            daily_consumption_kwh +                      # direct load
            (battery_charging_kwh - daily_consumption_kwh) +  # battery losses
            ely_daily_kwh                                 # electrolyzer
        ) * sizing_safety_factors.safety_margin_general

        pv_capacity_kwp = total_pv_energy_needed / (avg_psh * pv_eff_factor)
        pv_capacity_kwp *= sizing_safety_factors.pv_oversizing_factor

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
        )


    # ========== COST CALCULATIONS ==========

    @classmethod
    def _calculate_capex(cls, sizing: SizingOutput, cost_parameters, financial_assumptions) -> CapexBreakdownOutput:
        """Exact match to Excel CAPEX (no placeholder H2 storage cost)."""

        pv_capex = sizing.pv_capacity_kwp * cost_parameters.solar_pv_cost_usd_per_kwp
        battery_capex = sizing.battery_capacity_kwh * cost_parameters.battery_cost_usd_per_kwh
        electrolyzer_capex = sizing.electrolyzer_capacity_kw * cost_parameters.electrolyzer_cost_usd_per_kw
        fuel_cell_capex = sizing.fuel_cell_capacity_kw * cost_parameters.fuel_cell_cost_usd_per_kw

        # H2 storage cost = 0 in Excel model (we can add later)
        h2_storage_capex = 0.0

        component_sum = pv_capex + battery_capex + electrolyzer_capex + fuel_cell_capex + h2_storage_capex
        bop_capex = 0.0  # Excel had 0% BOS in final version

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
        """Calculate annual revenue from all streams.
        
        Revenue sources:
        1. H2 sales at specified price
        2. Excess electricity sales
        3. Heat recovery from electrolyzer
        4. Oxygen byproduct
        """
        # Daily production values
        h2_daily_kg = sizing.h2_daily_production_kg
        operation_days = 330  # assume default

        # Annual production
        h2_annual_kg = h2_daily_kg * operation_days
        
        # Oxygen byproduct
        o2_annual_kg = h2_annual_kg * cost_parameters.oxygen_production_ratio_kg_per_kg

        # H2 Sales Revenue - assume default price since not in new model
        h2_price = 3.0  # placeholder
        h2_revenue = h2_annual_kg * h2_price

        # Electricity sales (EaaS)
        avg_psh = (efficiencies_constants.jan_average_psh + efficiencies_constants.august_average_psh) / 2
        pv_daily_kwh = sizing.pv_capacity_kwp * avg_psh
        pv_annual_kwh = pv_daily_kwh * operation_days
        
        # Assume 10% excess available
        excess_electricity_kwh = pv_annual_kwh * 0.10
        electricity_revenue = excess_electricity_kwh * financial_assumptions.eaas_price_usd_per_kwh

        # Heat recovery from electrolyzer - assume default
        heat_price = 0.08  # placeholder
        pv_energy_for_heat = pv_annual_kwh * (1 - 0.75)  # 75% goes to H2, 25% available
        heat_available_kwh = pv_energy_for_heat
        heat_revenue = heat_available_kwh * heat_price

        # Oxygen sales
        oxygen_revenue = o2_annual_kg * cost_parameters.oxygen_price_usd_per_kg

        total_revenue = h2_revenue + electricity_revenue + heat_revenue + oxygen_revenue

        return RevenueStreamsOutput(
            h2_sales_revenue_usd_per_year=h2_revenue,
            electricity_sales_revenue_usd_per_year=electricity_revenue,
            heat_recovery_revenue_usd_per_year=heat_revenue,
            oxygen_byproduct_revenue_usd_per_year=oxygen_revenue,
            total_revenue_usd_per_year=total_revenue,
        )
    #==== Financial metrics calculations (NPV, IRR, Payback, LCOE, LCOH) with inflation and discounting ====#
        
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
        """Exact Excel match + revenue growth over EaaS contract years + EBITDA."""

        inv = capex.total_capex_after_subsidy_usd
        annual_ebitda_base = revenue.total_revenue_usd_per_year - opex.total_opex_usd_per_year

        discount = financial_assumptions.discount_rate_percent / 100
        life = int(financial_assumptions.system_lifetime_years)
        contract_years = int(financial_assumptions.eaas_contract_years)   # usually 10
        rev_growth = financial_assumptions.revenue_growth_percent / 100
        opex_inflation = financial_assumptions.opex_inflation_percent / 100

        # Build cash flows: revenue grows for first 10 years, then flat
        cash_flows = [-inv]
        for yr in range(1, life + 1):
            rev = revenue.total_revenue_usd_per_year * ((1 + rev_growth) ** min(yr - 1, contract_years - 1))
            opex_yr = opex.total_opex_usd_per_year * ((1 + opex_inflation) ** (yr - 1))
            cf = rev - opex_yr
            cash_flows.append(cf)

        npv = cls._calculate_npv(cash_flows, discount)
        irr = cls._calculate_irr(cash_flows) * 100
        payback = cls._calculate_payback_period(inv, annual_ebitda_base)

        # LCOE & LCOH (unchanged from previous correct version)
        annual_energy_kwh = sizing.daily_consumption_kwh * 365
        lcoe = cls._calculate_lcoe(inv, opex.total_opex_usd_per_year, annual_energy_kwh, discount, life)

        annual_h2_kg = sizing.h2_daily_production_kg * 365
        lcoh = cls._calculate_lcoh(inv, opex.total_opex_usd_per_year, annual_h2_kg, discount, life)

        return FinancialMetricsOutput(
            lcoe_usd_per_kwh=lcoe,
            lcoh_usd_per_kg=lcoh,
            irr_percent=irr,
            npv_usd=npv,
            payback_period_years=payback,
            ebitda_usd_per_year=annual_ebitda_base,   # base EBITDA (before growth)
        )


    # ========== FINANCIAL METRICS ==========

    # @classmethod
    # def _calculate_financial_metrics(
    #     cls,
    #     capex: CapexBreakdownOutput,
    #     opex: OpexBreakdownOutput,
    #     revenue: RevenueStreamsOutput,
    #     financial_assumptions,
    #     efficiencies_constants,
    #     sizing: SizingOutput,
    # ) -> FinancialMetricsOutput:
    #     """Calculate key financial metrics with inflation and discounting."""
    #     inv = capex.total_capex_after_subsidy_usd
    #     annual_revenue = revenue.total_revenue_usd_per_year
    #     annual_opex = opex.total_opex_usd_per_year
    #     annual_ebitda = annual_revenue - annual_opex

    #     discount = financial_assumptions.discount_rate_percent / 100
    #     life = int(financial_assumptions.system_lifetime_years)
    #     inflation = financial_assumptions.opex_inflation_percent / 100

    #     # Build cash flows with inflation
    #     cash_flows = [-inv]
    #     for yr in range(1, life + 1):
    #         # Inflate EBITDA for future years
    #         cf = annual_ebitda * ((1 + inflation) ** (yr - 1))
    #         cash_flows.append(cf)

    #     # Calculate NPV and IRR
    #     npv = cls._calculate_npv(cash_flows, discount)
    #     irr = cls._calculate_irr(cash_flows) * 100

    #     # Payback period (simple, without discounting)
    #     payback = cls._calculate_payback_period(inv, annual_ebitda) if annual_ebitda > 0 else float("inf")

    #     # LCOE and LCOH
    #     avg_psh = (efficiencies_constants.jan_average_psh + efficiencies_constants.august_average_psh) / 2
        
    #     # Annual electricity production from PV (kWh/year)
    #     annual_electricity_kwh = sizing.pv_capacity_kwp * avg_psh * 365
    #     lcoe = cls._calculate_lcoe(inv, annual_opex, annual_electricity_kwh, discount, life)
        
    #     # Annual hydrogen production (kg/year)
    #     annual_h2_kg = sizing.h2_daily_production_kg * 365
    #     lcoh = cls._calculate_lcoh(inv, annual_opex, annual_h2_kg, discount, life)

    #     return FinancialMetricsOutput(
    #         lcoe_usd_per_kwh=lcoe,
    #         lcoh_usd_per_kg=lcoh,
    #         irr_percent=irr,
    #         npv_usd=npv,
    #         payback_period_years=payback,
    #         ebitda_usd_per_year=annual_ebitda,
    #     )


    # @staticmethod
    # def _calculate_npv(cash_flows: List[float], discount_rate: float) -> float:
    #     """Calculate NPV given cash flows and discount rate."""
    #     return sum(cf / ((1 + discount_rate) ** t) for t, cf in enumerate(cash_flows))

    # @staticmethod
    # def _calculate_irr(cash_flows: List[float], guess: float = 0.1, iterations: int = 1000) -> float:
    #     """Calculate IRR using Newton-Raphson method."""
    #     rate = guess
    #     for _ in range(iterations):
    #         npv = sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cash_flows))
    #         d_npv = sum(-t * cf / ((1 + rate) ** (t + 1)) for t, cf in enumerate(cash_flows))
    #         if abs(d_npv) < 1e-6:
    #             break
    #         rate -= npv / d_npv
    #     return max(-0.99, rate)

    # @staticmethod
    # def _calculate_payback_period(investment: float, annual_cash_flow: float) -> float:
    #     """Simple payback period calculation."""
    #     return investment / annual_cash_flow if annual_cash_flow > 0 else float("inf")

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

    # @staticmethod
    # def _calculate_lcoh(
    #     investment: float,
    #     annual_opex: float,
    #     annual_h2_kg: float,
    #     discount_rate: float,
    #     project_life: int,
    # ) -> float:
    #     """Levelized Cost of Hydrogen."""
    #     if annual_h2_kg <= 0:
    #         return 0
    #     dr = discount_rate
    #     if dr > 0:
    #         annuity = dr * (1 + dr) ** project_life / ((1 + dr) ** project_life - 1)
    #     else:
    #         annuity = 1 / project_life
    #     return (investment * annuity + annual_opex) / annual_h2_kg


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
        sizing: SizingOutput,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        financial_assumptions,
        efficiencies_constants,
    ) -> List[SensitivityScenario]:
        """Generate sensitivity scenarios for key parameters."""
        # Simplified: return empty list for now
        return []
