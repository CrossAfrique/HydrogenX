"""
Health check endpoint for HydrogenX API
"""

from fastapi import APIRouter
from models.schemas import HealthCheckResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Check if the API is running and healthy"
)
async def health_check() -> HealthCheckResponse:
    """
    Simple health check endpoint
    
    Returns:
        HealthCheckResponse with status
    """
    return HealthCheckResponse(status="healthy")
