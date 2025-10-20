import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.simple_filter import SimpleFilter
from app.services.filter_service import FilterService

router = APIRouter()


@router.options("/")
async def options_simple_filters():
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.options("/{filter_id}")
async def options_simple_filter_by_id(filter_id: str):
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


@router.options("/{filter_id}/toggle")
async def options_toggle_filter(filter_id: str):
    """Handle OPTIONS requests for CORS preflight"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )


class SimpleFilterCreate(BaseModel):
    user_id: int
    name: str
    description: Optional[str] = None
    property_types: List[str] = []
    rental_types: List[str] = []
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    price_currency: str = "AMD"
    districts: List[str] = []
    has_balcony: Optional[bool] = None
    has_air_conditioning: Optional[bool] = None
    has_internet: Optional[bool] = None
    has_furniture: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_pool: Optional[bool] = None


class SimpleFilterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    property_types: Optional[List[str]] = None
    rental_types: Optional[List[str]] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    price_currency: Optional[str] = None
    districts: Optional[List[str]] = None
    has_balcony: Optional[bool] = None
    has_air_conditioning: Optional[bool] = None
    has_internet: Optional[bool] = None
    has_furniture: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_pool: Optional[bool] = None


def get_filter_service() -> FilterService:
    return FilterService()


@router.get("/user/{user_id}", response_model=List[SimpleFilter])
async def get_simple_filters_by_user(
    user_id: int,
    service: FilterService = Depends(get_filter_service)
):
    """Get simple filters for a specific user ID"""
    return await service.get_active_filters(user_id)


@router.get("/", response_model=List[SimpleFilter])
async def get_simple_filters(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    service: FilterService = Depends(get_filter_service)
):
    """Get simple filters, optionally filtered by user ID"""
    return await service.get_active_filters(user_id)


@router.get("/{filter_id}", response_model=SimpleFilter)
async def get_simple_filter(filter_id: str, service: FilterService = Depends(get_filter_service)):
    """Get a specific simple filter by ID"""
    try:
        filter_obj = await service.get_filter_by_id(filter_id)
        if not filter_obj:
            raise HTTPException(status_code=404, detail="Filter not found")
        return filter_obj
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/", response_model=dict)
async def create_simple_filter(
    filter_data: SimpleFilterCreate, service: FilterService = Depends(get_filter_service)
):
    """Create a new simple filter"""
    try:
        # Additional validation
        if not filter_data.name or not filter_data.name.strip():
            raise HTTPException(status_code=400, detail="Filter name is required")
        
        if filter_data.user_id <= 0:
            raise HTTPException(status_code=400, detail="Invalid user ID")
        
        # Validate room range
        if filter_data.min_rooms and filter_data.max_rooms and filter_data.min_rooms > filter_data.max_rooms:
            raise HTTPException(status_code=400, detail="min_rooms cannot be greater than max_rooms")
        
        # Validate area range
        if filter_data.min_area and filter_data.max_area and filter_data.min_area > filter_data.max_area:
            raise HTTPException(status_code=400, detail="min_area cannot be greater than max_area")
        
        # Sanitize string inputs
        filter_data.name = filter_data.name.strip()
        if filter_data.description:
            filter_data.description = filter_data.description.strip()
        
        filter_id = await service.create_filter(filter_data.dict())
        return {"id": filter_id, "message": "Filter created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{filter_id}", response_model=dict)
async def update_simple_filter(
    filter_id: str, 
    filter_data: SimpleFilterUpdate, 
    user_id: int = Query(..., description="User ID for ownership verification"),
    service: FilterService = Depends(get_filter_service)
):
    """Update an existing simple filter"""
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting PATCH update for filter %s by user %s", filter_id, user_id)

        # Get current filter state
        current_filter = await service.get_filter_by_id(filter_id)
        if not current_filter:
            raise HTTPException(status_code=404, detail="Filter not found")
        
        # Check ownership
        if current_filter.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only update your own filters")
        
        logger.info("Current filter state: %s", current_filter)

        # Include only non-None values to avoid overwriting required fields
        update_data = {k: v for k, v in filter_data.dict().items() if v is not None}
        logger.info("Update data: %s", update_data)

        success = await service.update_filter(filter_id, update_data)
        if success:
            # Get updated filter state
            updated_filter = await service.get_filter_by_id(filter_id)
            logger.info("Updated filter state: %s", updated_filter)

            response = {"message": "Filter updated successfully", "filter": updated_filter}
            logger.info("Returning response: %s", response)
            return response
        else:
            logger.error("Filter %s not found", filter_id)
            raise HTTPException(status_code=404, detail="Filter not found")
    except Exception as e:
        logger.error("Error updating filter %s: %s", filter_id, e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{filter_id}", response_model=dict)
async def delete_simple_filter(
    filter_id: str, 
    user_id: int = Query(..., description="User ID for ownership verification"),
    service: FilterService = Depends(get_filter_service)
):
    """Delete a simple filter"""
    try:
        # Check ownership before deletion
        current_filter = await service.get_filter_by_id(filter_id)
        if not current_filter:
            raise HTTPException(status_code=404, detail="Filter not found")
        
        if current_filter.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only delete your own filters")
        
        success = await service.delete_filter(filter_id)
        if success:
            return {"message": "Filter deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Filter not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{filter_id}/toggle", response_model=dict)
async def toggle_simple_filter(
    filter_id: str, 
    user_id: int = Query(..., description="User ID for ownership verification"),
    service: FilterService = Depends(get_filter_service)
):
    """Toggle filter active status"""
    try:
        # Check ownership before toggle
        current_filter = await service.get_filter_by_id(filter_id)
        if not current_filter:
            raise HTTPException(status_code=404, detail="Filter not found")
        
        if current_filter.user_id != user_id:
            raise HTTPException(status_code=403, detail="You can only toggle your own filters")
        
        success = await service.toggle_filter_status(filter_id)
        if success:
            return {"message": "Filter status toggled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Filter not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
