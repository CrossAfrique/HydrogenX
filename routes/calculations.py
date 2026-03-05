"""
Calculation endpoints for HydrogenX API
"""

from fastapi import APIRouter, HTTPException, status
import logging

from models.schemas import SingleSiteInput
from models.output import SingleSiteOutput

from services.calculations import HydrogenCalculator

# portfolio imports (left for future use)
from models.schemas import PortfolioInput, PortfolioOutput

router = APIRouter(prefix="/api/v1", tags=["calculations"])
logger = logging.getLogger(__name__)


@router.post(
    "/calculate_single_site",
    response_model=SingleSiteOutput,
    summary="Calculate Single Site Metrics",
    description="Calculate energy, sizing, financial metrics, and revenue streams for a single site"
)
async def calculate_single_site(request: SingleSiteInput) -> SingleSiteOutput:
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
        request: SingleSiteInput with all parameters
        
    Returns:
        SingleSiteOutput with all calculated results
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        logger.info(f"Calculating single site: {request.site_name}")
        
        # Perform calculation using the new HydrogenCalculator
        result = HydrogenCalculator.calculate_single_site(request)
        
        logger.info(f"Single site calculation completed for {request.site_name}")
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
