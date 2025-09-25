from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.models.price_filter import PriceFilter
from app.services.price_filter_service import PriceFilterService

router = APIRouter()


class PriceFilterCreate(BaseModel):
    """Request model for creating a price filter"""
    filter_id: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: str
    is_active: bool = True


class PriceFilterUpdate(BaseModel):
    """Request model for updating a price filter"""
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


class PriceFilterResponse(BaseModel):
    """Response model for price filter"""
    id: str
    filter_id: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: str
    is_active: bool
    created_at: str
    updated_at: str


def get_price_filter_service() -> PriceFilterService:
    """Dependency to get price filter service"""
    return PriceFilterService()


@router.get("/filters/{filter_id}/price-filters", response_model=List[PriceFilterResponse])
async def get_price_filters(
    filter_id: str,
    service: PriceFilterService = Depends(get_price_filter_service)
):
    """Get all price filters for a specific SimpleFilter"""
    try:
        price_filters = await service.get_price_filters_by_filter_id(filter_id)
        
        return [
            PriceFilterResponse(
                id=pf.id or "",
                filter_id=pf.filter_id,
                min_price=pf.min_price,
                max_price=pf.max_price,
                currency=pf.currency,
                is_active=pf.is_active,
                created_at=pf.created_at.isoformat(),
                updated_at=pf.updated_at.isoformat()
            )
            for pf in price_filters
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting price filters: {str(e)}"
        )


@router.post("/price-filters", response_model=dict)
async def create_price_filter(
    price_filter_data: PriceFilterCreate,
    service: PriceFilterService = Depends(get_price_filter_service)
):
    """Create a new price filter"""
    try:
        # Validate price range
        if price_filter_data.min_price is not None and price_filter_data.max_price is not None:
            if price_filter_data.min_price > price_filter_data.max_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="min_price cannot be greater than max_price"
                )
        
        # Validate at least one price is specified
        if price_filter_data.min_price is None and price_filter_data.max_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of min_price or max_price must be specified"
            )
        
        price_filter = PriceFilter(
            filter_id=price_filter_data.filter_id,
            min_price=price_filter_data.min_price,
            max_price=price_filter_data.max_price,
            currency=price_filter_data.currency,
            is_active=price_filter_data.is_active
        )
        
        price_filter_id = await service.create_price_filter(price_filter)
        
        return {
            "id": price_filter_id,
            "message": "Price filter created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating price filter: {str(e)}"
        )


@router.put("/price-filters/{price_filter_id}", response_model=dict)
async def update_price_filter(
    price_filter_id: str,
    update_data: PriceFilterUpdate,
    service: PriceFilterService = Depends(get_price_filter_service)
):
    """Update a price filter"""
    try:
        # Validate price range if both are provided
        if (update_data.min_price is not None and 
            update_data.max_price is not None and 
            update_data.min_price > update_data.max_price):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="min_price cannot be greater than max_price"
            )
        
        # Convert to dict, removing None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        success = await service.update_price_filter(price_filter_id, update_dict)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price filter not found"
            )
        
        return {"message": "Price filter updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating price filter: {str(e)}"
        )


@router.delete("/price-filters/{price_filter_id}", response_model=dict)
async def delete_price_filter(
    price_filter_id: str,
    service: PriceFilterService = Depends(get_price_filter_service)
):
    """Delete a price filter"""
    try:
        success = await service.delete_price_filter(price_filter_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price filter not found"
            )
        
        return {"message": "Price filter deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting price filter: {str(e)}"
        )
