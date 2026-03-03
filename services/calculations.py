"""
HydrogenX calculation service: single-site energy and financial models
The HydrogenCalculator class encapsulates the full logic required for
one-site sizing, revenue, cost and financial analysis.  A separate
portfolio calculator will be built later.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict

import math

from models.schemas import SingleSiteInput
from models.output import (
    SingleSiteOutput,
    SizingOutput,
    CapexBreakdownOutput,
    OpexBreakdownOutput,
    RevenueStreamsOutput,
    FinancialMetricsOutput,
    MonthlyDataPoint,
    SensitivityScenario,
)


class HydrogenCalculator:
    """Per‑site calculation logic for HydrogenX.

    Everything needed to produce the frontend payload for a single
    installation lives here.  The public entrypoint is
    :meth:`calculate_single_site`, which returns a
    :class:`models.output.SingleSiteOutput` instance ready for
    serialization.
    """

    # ------------------------------------------------------------------
    # static cost parameters (can later be externalised)
    # ------------------------------------------------------------------
    COST_DATA = {
        "pv": {"capex_per_kwp": 800, "opex_percent_per_year": 0.5},
        "battery": {"capex_per_kwh": 300, "opex_percent_per_year": 1.0},
        "electrolyzer": {"capex_per_kw": 1200, "opex_percent_per_year": 2.0},
        "h2_storage": {"capex_per_kg": 50, "opex_percent_per_year": 1.5},
        "fuel_cell": {"capex_per_kw": 1500, "opex_percent_per_year": 2.5},
        "bop": {"capex_percent": 15, "opex_percent_per_year": 1.0},
    }

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    @classmethod
    def calculate_single_site(cls, input_data: SingleSiteInput) -> SingleSiteOutput:
        """Perform the full single‑site calculation.

        The method implements the complete chain described in the
        project specification:

        * sizing for all components
        * CAPEX & OPEX calculation
        * revenue streams (electricity, heat, oxygen)
        * monthly breakdown for charting
        * financial metrics (LCOE, LCOH, IRR, NPV, payback, EBITDA)
        * sensitivity analysis on a handful of key parameters

        :param input_data: user‑supplied payload from the frontend
        :returns: a fully populated :class:`SingleSiteOutput`
        """
        gp = input_data.global_params

        # ------------------------------------------------------------------
        # energy sizing and production
        # ------------------------------------------------------------------
        daily_energy = cls._calculate_daily_pv_energy(
            input_data.solar_pv.capacity_kwp,
            input_data.solar_pv.performance_ratio,
            gp.peak_sun_hours_per_day,
        )

        sizing = cls._calculate_sizing(input_data, daily_energy)

        # ------------------------------------------------------------------
        # cost breakdowns
        # ------------------------------------------------------------------
        capex = cls._calculate_capex(input_data, sizing)
        opex = cls._calculate_opex(input_data, sizing, capex)

        # ------------------------------------------------------------------
        # revenues
        # ------------------------------------------------------------------
        h2_annual_kg = cls._calculate_h2_production(
            daily_energy, input_data.electrolyzer.specific_energy_kwh_per_kg, gp.operation_days_per_year
        )
        revenue = cls._calculate_revenue(
            daily_energy, h2_annual_kg, input_data, gp
        )

        # ------------------------------------------------------------------
        # financial metrics
        # ------------------------------------------------------------------
        financial = cls._calculate_financial_metrics(capex, opex, revenue, gp, input_data)

        # ------------------------------------------------------------------
        # monthly data for chart
        # ------------------------------------------------------------------
        monthly = cls._calculate_monthly_data(
            daily_energy, h2_annual_kg, opex.total_opex_usd_per_year / 12, input_data, gp
        )

        # ------------------------------------------------------------------
        # sensitivity analysis
        # ------------------------------------------------------------------
        sensitivity = cls._calculate_sensitivity(
            input_data, sizing, capex, opex, revenue, gp
        )

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

    # ------------------------------------------------------------------
    # helper calculation blocks
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_daily_pv_energy(
        pv_capacity_kwp: float, performance_ratio: float, peak_sun_hours: float
    ) -> float:
        """Daily energy from PV using a user‑supplied peak sun hours."""
        return pv_capacity_kwp * performance_ratio * peak_sun_hours

    @staticmethod
    def _calculate_sizing(input_data: SingleSiteInput, daily_energy: float) -> SizingOutput:
        """Derive basic component sizes.

        Battery usable capacity is capacity * (1 - reserve SOC).
        Hydrogen storage uses autonomy hours and daily daily production.
        """
        pv = input_data.solar_pv.capacity_kwp
        batt_gross = input_data.battery_storage.capacity_kwh
        batt_usable = batt_gross * (1 - input_data.battery_storage.reserve_soc_percent / 100)

        electrolyzer_kw = input_data.electrolyzer.power_kw

        h2_daily_kg = daily_energy / input_data.electrolyzer.specific_energy_kwh_per_kg
        h2_storage = h2_daily_kg * (input_data.hydrogen_storage.autonomy_hours / 24)

        fc_kw = input_data.fuel_cell.power_rating_kw

        return SizingOutput(
            pv_capacity_kwp=pv,
            battery_capacity_kwh=batt_gross,
            electrolyzer_capacity_kw=electrolyzer_kw,
            h2_storage_capacity_kg=h2_storage,
            fuel_cell_capacity_kw=fc_kw,
        )

    @classmethod
    def _calculate_capex(
        cls, input_data: SingleSiteInput, sizing: SizingOutput, capex_factors: Dict[str, float] = None
    ) -> CapexBreakdownOutput:
        """CAPEX breakdown with optional component multipliers."""
        c = cls.COST_DATA
        factors = capex_factors or {}

        pv_cost = sizing.pv_capacity_kwp * c["pv"]["capex_per_kwp"] * factors.get("pv", 1.0)
        batt_cost = sizing.battery_capacity_kwh * c["battery"]["capex_per_kwh"] * factors.get("battery", 1.0)
        electrolyzer_cost = sizing.electrolyzer_capacity_kw * c["electrolyzer"]["capex_per_kw"] * factors.get("electrolyzer", 1.0)
        h2_cost = sizing.h2_storage_capacity_kg * c["h2_storage"]["capex_per_kg"] * factors.get("h2_storage", 1.0)
        fc_cost = sizing.fuel_cell_capacity_kw * c["fuel_cell"]["capex_per_kw"] * factors.get("fuel_cell", 1.0)

        component_sum = pv_cost + batt_cost + electrolyzer_cost + h2_cost + fc_cost
        bop_cost = component_sum * (c["bop"]["capex_percent"] / 100)
        total = component_sum + bop_cost
        after_sub = total * (1 - input_data.global_params.subsidy_percent / 100)

        return CapexBreakdownOutput(
            pv_capex_usd=pv_cost,
            battery_capex_usd=batt_cost,
            electrolyzer_capex_usd=electrolyzer_cost,
            h2_storage_capex_usd=h2_cost,
            fuel_cell_capex_usd=fc_cost,
            bop_capex_usd=bop_cost,
            total_capex_usd=total,
            after_subsidy_capex_usd=after_sub,
        )

    @classmethod
    def _calculate_opex(
        cls, input_data: SingleSiteInput, sizing: SizingOutput, capex: CapexBreakdownOutput
    ) -> OpexBreakdownOutput:
        """Annual OPEX split into two groups, inflation handled later in cash flow."""
        c = cls.COST_DATA

        pv_batt_opex = capex.pv_capex_usd * (c["pv"]["opex_percent_per_year"] / 100)
        pv_batt_opex += capex.battery_capex_usd * (c["battery"]["opex_percent_per_year"] / 100)

        elec_fc_opex = capex.electrolyzer_capex_usd * (c["electrolyzer"]["opex_percent_per_year"] / 100)
        elec_fc_opex += capex.fuel_cell_capex_usd * (c["fuel_cell"]["opex_percent_per_year"] / 100)

        # add h2 storage + bop
        h2_opex = capex.h2_storage_capex_usd * (c["h2_storage"]["opex_percent_per_year"] / 100)
        bop_opex = capex.bop_capex_usd * (c["bop"]["opex_percent_per_year"] / 100)

        total = pv_batt_opex + elec_fc_opex + h2_opex + bop_opex
        return OpexBreakdownOutput(
            pv_battery_opex_usd_per_year=pv_batt_opex,
            electrolyzer_fc_opex_usd_per_year=elec_fc_opex,
            total_opex_usd_per_year=total,
        )

    @staticmethod
    def _calculate_h2_production(
        daily_energy: float, specific_kwh_per_kg: float, operation_days: int
    ) -> float:
        return (daily_energy / specific_kwh_per_kg) * operation_days

    @classmethod
    def _calculate_revenue(
        cls,
        daily_energy: float,
        annual_h2_kg: float,
        input_data: SingleSiteInput,
        gp,
    ) -> RevenueStreamsOutput:
        """Compute annual revenues taking into account baseload and grid limit."""
        # electricity generated per year
        annual_pv = daily_energy * gp.operation_days_per_year
        thermal_load = input_data.thermal_baseload.capacity_kwth * gp.operation_days_per_year
        excess = max(annual_pv - thermal_load, 0)

        # limit by grid import (export) capacity
        grid_limit_energy = input_data.generator_grid.grid_import_limit_kw * gp.operation_days_per_year
        export_energy = min(excess, grid_limit_energy)

        elec_rev = export_energy * gp.electricity_price_usd_per_kwh

        heat_recovered = annual_pv * (input_data.electrolyzer.heat_recovery_percent / 100)
        heat_available = max(heat_recovered - thermal_load, 0)
        heat_rev = heat_available * gp.heat_price_usd_per_kwh

        o2_kg = annual_h2_kg * 8
        o2_rev = o2_kg * gp.oxygen_price_usd_per_kg

        total_rev = elec_rev + heat_rev + o2_rev
        return RevenueStreamsOutput(
            electricity_revenue_usd_per_year=elec_rev,
            heat_revenue_usd_per_year=heat_rev,
            oxygen_revenue_usd_per_year=o2_rev,
            total_revenue_usd_per_year=total_rev,
        )

    @classmethod
    def _calculate_financial_metrics(
        cls,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        gp,
        input_data: SingleSiteInput,
    ) -> FinancialMetricsOutput:
        inv = capex.after_subsidy_capex_usd
        annual_rev = revenue.total_revenue_usd_per_year
        annual_opex = opex.total_opex_usd_per_year
        annual_ebitda = annual_rev - annual_opex

        discount = gp.discount_rate_percent / 100
        life = gp.project_lifetime_years
        inflation = gp.inflation_percent / 100

        # cash flows with inflation applied to EBITDA
        cash_flows = [-inv]
        for yr in range(1, life + 1):
            cf = annual_ebitda * ((1 + inflation) ** (yr - 1))
            cash_flows.append(cf)

        npv = cls._calculate_npv(cash_flows, discount)
        irr = cls._calculate_irr(cash_flows) * 100
        payback = cls._calculate_payback_period(inv, annual_ebitda)

        # energy metrics
        annual_energy = gp.operation_days_per_year * gp.peak_sun_hours_per_day * input_data.solar_pv.capacity_kwp * 0.8
        lcoe = cls._calculate_lcoe(inv, annual_opex, annual_energy, discount, life)
        annual_h2 = (gp.operation_days_per_year * gp.peak_sun_hours_per_day * input_data.solar_pv.capacity_kwp) / input_data.electrolyzer.specific_energy_kwh_per_kg
        lcoh = cls._calculate_lcoh(inv, annual_opex, annual_h2, discount, life)

        return FinancialMetricsOutput(
            lcoe_usd_per_kwh=lcoe,
            lcoh_usd_per_kg=lcoh,
            irr_percent=irr,
            npv_usd=npv,
            payback_period_years=payback,
            ebitda_usd_per_year=annual_ebitda,
        )

    # ------------------------------------------------------------------
    # financial math helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_npv(cash_flows: List[float], discount_rate: float) -> float:
        return sum(cf / ((1 + discount_rate) ** t) for t, cf in enumerate(cash_flows))

    @staticmethod
    def _calculate_irr(cash_flows: List[float], guess: float = 0.1, iterations: int = 1000) -> float:
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
        return investment / annual_cash_flow if annual_cash_flow > 0 else float("inf")

    @staticmethod
    def _calculate_lcoe(
        investment: float,
        annual_opex: float,
        annual_energy_kwh: float,
        discount_rate: float,
        project_life: int,
    ) -> float:
        if annual_energy_kwh <= 0:
            return 0
        annuity = discount_rate * (1 + discount_rate) ** project_life / ((1 + discount_rate) ** project_life - 1)
        return (investment * annuity + annual_opex) / annual_energy_kwh

    @staticmethod
    def _calculate_lcoh(
        investment: float,
        annual_opex: float,
        annual_h2_kg: float,
        discount_rate: float,
        project_life: int,
    ) -> float:
        if annual_h2_kg <= 0:
            return 0
        annuity = discount_rate * (1 + discount_rate) ** project_life / ((1 + discount_rate) ** project_life - 1)
        return (investment * annuity + annual_opex) / annual_h2_kg

    # ------------------------------------------------------------------
    # charting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_monthly_data(
        daily_energy: float,
        annual_h2_kg: float,
        monthly_opex: float,
        input_data: SingleSiteInput,
        gp,
    ) -> List[MonthlyDataPoint]:
        """Create 12 uniform monthly points for stacked bar chart."""
        data = []
        monthly_energy = daily_energy * 30
        monthly_h2 = annual_h2_kg / 12
        for m in range(1, 13):
            elec = monthly_energy * 0.8 * gp.electricity_price_usd_per_kwh
            heat = monthly_energy * (input_data.electrolyzer.heat_recovery_percent / 100) * gp.heat_price_usd_per_kwh
            o2 = monthly_h2 * 8 * gp.oxygen_price_usd_per_kg
            total_rev = elec + heat + o2
            ebitda = total_rev - monthly_opex
            data.append(
                MonthlyDataPoint(
                    month=m,
                    electricity_revenue=elec,
                    heat_revenue=heat,
                    oxygen_revenue=o2,
                    total_opex=monthly_opex,
                    ebitda=ebitda,
                )
            )
        return data

    # ------------------------------------------------------------------
    # sensitivity analysis
    # ------------------------------------------------------------------

    @classmethod
    def _calculate_sensitivity(
        cls,
        input_data: SingleSiteInput,
        sizing: SizingOutput,
        capex: CapexBreakdownOutput,
        opex: OpexBreakdownOutput,
        revenue: RevenueStreamsOutput,
        gp,
    ) -> List[SensitivityScenario]:
        """Generate a few simple sensitivity scenarios.

        Scenarios include ±10% changes to the discount rate, overall
        capex and electrolyzer cost.
        """
        scenarios: List[SensitivityScenario] = []

        base_fin = cls._calculate_financial_metrics(capex, opex, revenue, gp, input_data)
        scenarios.append(SensitivityScenario(description="base", financial_metrics=base_fin))

        # discount rate ±10%
        for factor in (0.9, 1.1):
            gp_mod = gp.model_copy(update={"discount_rate_percent": gp.discount_rate_percent * factor})
            fin = cls._calculate_financial_metrics(capex, opex, revenue, gp_mod, input_data)
            scenarios.append(
                SensitivityScenario(
                    description=f"discount_rate_{int((factor-1)*100)}%",
                    financial_metrics=fin,
                )
            )

        # overall capex ±10%
        for factor in (0.9, 1.1):
            capex_mod = cls._calculate_capex(input_data, sizing, {"pv": factor, "battery": factor, "electrolyzer": factor, "h2_storage": factor, "fuel_cell": factor})
            fin = cls._calculate_financial_metrics(capex_mod, opex, revenue, gp, input_data)
            scenarios.append(
                SensitivityScenario(
                    description=f"capex_{int((factor-1)*100)}%",
                    financial_metrics=fin,
                )
            )

        # electrolyzer cost ±10%
        for factor in (0.9, 1.1):
            capex_mod = cls._calculate_capex(input_data, sizing, {"electrolyzer": factor})
            fin = cls._calculate_financial_metrics(capex_mod, opex, revenue, gp, input_data)
            scenarios.append(
                SensitivityScenario(
                    description=f"electrolyzer_cost_{int((factor-1)*100)}%",
                    financial_metrics=fin,
                )
            )

        return scenarios
