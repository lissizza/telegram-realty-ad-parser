from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app.db.mongodb import mongodb
from app.models.telegram import RealEstateAd

router = APIRouter()


@router.get("/", response_model=List[RealEstateAd])
async def get_real_estate_ads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    property_type: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    district: Optional[str] = None,
):
    """Get real estate ads with filtering and pagination"""
    db = mongodb.get_database()
    query: Dict[str, Any] = {}

    if property_type:
        query["property_type"] = property_type
    if min_price is not None:
        query["price"] = {"$gte": min_price}
    if max_price is not None:
        if "price" in query:
            query["price"]["$lte"] = max_price
        else:
            query["price"] = {"$lte": max_price}
    if district:
        query["district"] = {"$regex": district, "$options": "i"}

    ads = []
    cursor = db.real_estate_ads.find(query).skip(skip).limit(limit).sort("created_at", -1)
    async for ad_doc in cursor:
        ad_doc["id"] = str(ad_doc["_id"])
        ad = RealEstateAd(**ad_doc)
        # Copy rooms_count to rooms for API compatibility
        if ad.rooms_count is not None:
            ad.rooms = ad.rooms_count
        ads.append(ad)
    return ads


@router.get("/{ad_id}", response_model=RealEstateAd)
async def get_real_estate_ad(ad_id: str):
    """Get a specific real estate ad"""
    db = mongodb.get_database()
    ad_doc = await db.real_estate_ads.find_one({"_id": ObjectId(ad_id)})
    if not ad_doc:
        raise HTTPException(status_code=404, detail="Real estate ad not found")
    ad_doc["id"] = str(ad_doc["_id"])
    ad = RealEstateAd(**ad_doc)
    # Copy rooms_count to rooms for API compatibility
    if ad.rooms_count is not None:
        ad.rooms = ad.rooms_count
    return ad


@router.delete("/{ad_id}")
async def delete_real_estate_ad(ad_id: str):
    """Delete a real estate ad"""
    db = mongodb.get_database()
    result = await db.real_estate_ads.delete_one({"_id": ObjectId(ad_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Real estate ad not found")
    return {"message": "Real estate ad deleted successfully"}


@router.get("/stats/summary")
async def get_real_estate_stats():
    """Get real estate statistics"""
    db = mongodb.get_database()

    # Total count
    total_count = await db.real_estate_ads.count_documents({})

    # Property type distribution
    property_types = await db.real_estate_ads.aggregate(
        [{"$group": {"_id": "$property_type", "count": {"$sum": 1}}}]
    ).to_list(None)

    # Price statistics
    price_stats = await db.real_estate_ads.aggregate(
        [
            {"$match": {"price": {"$exists": True, "$ne": None}}},
            {
                "$group": {
                    "_id": None,
                    "avg_price": {"$avg": "$price"},
                    "min_price": {"$min": "$price"},
                    "max_price": {"$max": "$price"},
                }
            },
        ]
    ).to_list(None)

    # District distribution
    districts = await db.real_estate_ads.aggregate(
        [
            {"$match": {"district": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$district", "count": {"$sum": 1}}},
        ]
    ).to_list(None)

    return {
        "total_count": total_count,
        "property_types": property_types,
        "price_stats": price_stats[0] if price_stats else None,
        "districts": districts,
    }
