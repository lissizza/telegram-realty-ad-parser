from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.simple_filter_service import SimpleFilterService
from app.models.simple_filter import SimpleFilter

router = APIRouter()


class SimpleFilterCreate(BaseModel):
    name: str
    description: str = None
    property_types: List[str] = []
    rental_types: List[str] = []
    min_rooms: int = None
    max_rooms: int = None
    min_area: float = None
    max_area: float = None
    min_price_amd: int = None
    max_price_amd: int = None
    min_price_usd: float = None
    max_price_usd: float = None
    districts: List[str] = []
    has_balcony: bool = None
    has_air_conditioning: bool = None
    has_internet: bool = None
    has_furniture: bool = None
    has_parking: bool = None
    has_garden: bool = None
    has_pool: bool = None


class SimpleFilterUpdate(BaseModel):
    name: str = None
    description: str = None
    property_types: List[str] = None
    rental_types: List[str] = None
    min_rooms: int = None
    max_rooms: int = None
    min_area: float = None
    max_area: float = None
    min_price_amd: int = None
    max_price_amd: int = None
    min_price_usd: float = None
    max_price_usd: float = None
    districts: List[str] = None
    has_balcony: bool = None
    has_air_conditioning: bool = None
    has_internet: bool = None
    has_furniture: bool = None
    has_parking: bool = None
    has_garden: bool = None
    has_pool: bool = None


def get_simple_filter_service() -> SimpleFilterService:
    return SimpleFilterService()


@router.get("/", response_model=List[SimpleFilter])
async def get_simple_filters(
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Get all simple filters"""
    return await service.get_active_filters()


@router.get("/{filter_id}", response_model=SimpleFilter)
async def get_simple_filter(
    filter_id: str,
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Get a specific simple filter by ID"""
    try:
        filter_obj = await service.get_filter_by_id(filter_id)
        if not filter_obj:
            raise HTTPException(status_code=404, detail="Filter not found")
        return filter_obj
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=dict)
async def create_simple_filter(
    filter_data: SimpleFilterCreate,
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Create a new simple filter"""
    try:
        filter_id = await service.create_filter(filter_data.dict())
        return {"id": filter_id, "message": "Filter created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{filter_id}", response_model=dict)
async def update_simple_filter(
    filter_id: str,
    filter_data: SimpleFilterUpdate,
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Update an existing simple filter"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Starting PATCH update for filter {filter_id}")

        # Get current filter state
        current_filter = await service.get_filter_by_id(filter_id)
        logger.info(f"Current filter state: {current_filter}")

        # Remove None values
        update_data = {k: v for k, v in filter_data.dict().items() if v is not None}
        logger.info(f"Update data: {update_data}")

        success = await service.update_filter(filter_id, update_data)
        if success:
            # Get updated filter state
            updated_filter = await service.get_filter_by_id(filter_id)
            logger.info(f"Updated filter state: {updated_filter}")

            response = {"message": "Filter updated successfully", "filter": updated_filter}
            logger.info(f"Returning response: {response}")
            return response
        else:
            logger.error(f"Filter {filter_id} not found")
            raise HTTPException(status_code=404, detail="Filter not found")
    except Exception as e:
        logger.error(f"Error updating filter {filter_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{filter_id}", response_model=dict)
async def delete_simple_filter(
    filter_id: str,
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Delete a simple filter"""
    try:
        success = await service.delete_filter(filter_id)
        if success:
            return {"message": "Filter deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Filter not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{filter_id}/toggle", response_model=dict)
async def toggle_simple_filter(
    filter_id: str,
    service: SimpleFilterService = Depends(get_simple_filter_service)
):
    """Toggle filter active status"""
    try:
        success = await service.toggle_filter_status(filter_id)
        if success:
            return {"message": "Filter status toggled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Filter not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



