"""
Calculation endpoints for HydrogenX API
"""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List
import logging

from models.schemas import SingleSiteInput, HourlySimulationRequest, PortfolioInput, PortfolioOutput
from models.output import SingleSiteOutput, HourlySnapshot, OptimizationResult

from services.calculations import HydrogenCalculator

router = APIRouter(prefix="", tags=["calculations"])
logger = logging.getLogger(__name__)


@router.post(
    "/calculate_single_site",
    response_model=SingleSiteOutput,
    summary="Calculate Single Site Metrics",
    description="Calculate energy, sizing, financial metrics, and revenue streams for a single site"
)
async def calculate_single_site(request: dict) -> SingleSiteOutput:
    """
    Calculate comprehensive metrics for a single hydrogen/energy site
    
    Accepts all sidebar parameters and returns:
    - System sizing for all components
    - CAPEX breakdown by component
    - OPEX split
    - Revenue streams (electricity, heat, oxygen)
    - Financial metrics (LCOE, LCOH, IRR, NPV, Payback)
    - Monthly revenue vs OPEX data for charting
    
    Args:
        request: raw payload dictionary from frontend
        
    Returns:
        SingleSiteOutput with all calculated results
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        single_site_input = HydrogenCalculator.build_single_site_input(request)
        logger.info(f"Calculating single site: {single_site_input.site_name}")
        
        # Perform calculation using the new HydrogenCalculator
        result = HydrogenCalculator.calculate_single_site(single_site_input)
        
        logger.info(f"Single site calculation completed for {single_site_input.site_name}")
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Calculation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during calculation"
        )


@router.get(
    "/location_ghi",
    response_model=List[float],
    summary="Estimate monthly PSH for a location",
    description="Return an estimated 12-month profile of peak sun hours based on latitude/longitude"
)
async def location_ghi(lat: float = Query(..., description="Latitude of the location"), lon: float = Query(..., description="Longitude of the location")) -> List[float]:
    try:
        return HydrogenCalculator.estimate_location_monthly_psh(lat, lon)
    except Exception as e:
        logger.error(f"Location GHI error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not estimate location GHI values"
        )


@router.post(
    "/simulate_hourly",
    response_model=List[HourlySnapshot],
    summary="Run detailed hourly energy simulation",
    description="Simulate 8760 hours of PV, battery, hydrogen production, and fuel cell dispatch"
)
async def simulate_hourly(request: HourlySimulationRequest) -> List[HourlySnapshot]:
    try:
        snap = HydrogenCalculator.simulate_hourly(request.input_data, request.hourly_ghi)
        return snap
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Hourly simulation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete hourly simulation"
        )


@router.post(
    "/optimize_sizing",
    response_model=OptimizationResult,
    summary="Optimize battery and hydrogen sizing",
    description="Find the size pair that minimizes LCOE for a single site"
)
async def optimize_sizing(request: SingleSiteInput) -> OptimizationResult:
    try:
        return HydrogenCalculator.optimize_sizing(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Optimization error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Optimization failed"
        )


@router.post(
    "/calculate_portfolio",
    response_model=PortfolioOutput,
    summary="Calculate Portfolio Metrics",
    description="Calculate aggregated metrics for a portfolio of sites"
)
async def calculate_portfolio(request: PortfolioInput) -> PortfolioOutput:
    """
    Calculate comprehensive metrics for a portfolio of hydrogen/energy sites
    
    Accepts array of sites and returns:
    - Individual site results
    - Aggregated portfolio metrics
    - Aggregated monthly revenue vs OPEX data
    
    Args:
        request: PortfolioInput with array of sites
        
    Returns:
        PortfolioOutput with individual and aggregated results
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        logger.info(f"Calculating portfolio: {request.portfolio_name} with {len(request.sites)} sites")
        
        # Perform portfolio calculation using HydrogenCalculator
        result = HydrogenCalculator.calculate_portfolio(request)
        
        logger.info(f"Portfolio calculation completed for {request.portfolio_name}")
        return result
        
    except Exception as e:
        logger.error(f"Portfolio calculation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during portfolio calculation"
        )
