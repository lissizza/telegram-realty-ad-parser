from typing import List

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from app.models.telegram import RealEstateAd
from app.db.mongodb import mongodb

router = APIRouter()


@router.get("/", response_model=List[RealEstateAd])
async def get_real_estate_ads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    property_type: str = None,
    min_price: int = None,
    max_price: int = None,
    district: str = None,
):
    """Get real estate ads with filtering and pagination"""
    db = mongodb.get_database()
    query = {}
    
    if property_type:
        query["property_type"] = property_type
    if min_price is not None:
        query["price_amd"] = {"$gte": min_price}
    if max_price is not None:
        if "price_amd" in query:
            query["price_amd"]["$lte"] = max_price
        else:
            query["price_amd"] = {"$lte": max_price}
    if district:
        query["district"] = {"$regex": district, "$options": "i"}
    
    ads = []
    cursor = db.real_estate_ads.find(query).skip(skip).limit(limit).sort("created_at", -1)
    async for ad_doc in cursor:
        ad_doc["id"] = str(ad_doc["_id"])
        ads.append(RealEstateAd(**ad_doc))
    return ads


@router.get("/{ad_id}", response_model=RealEstateAd)
async def get_real_estate_ad(ad_id: str):
    """Get a specific real estate ad"""
    db = mongodb.get_database()
    ad_doc = await db.real_estate_ads.find_one({"_id": ObjectId(ad_id)})
    if not ad_doc:
        raise HTTPException(status_code=404, detail="Real estate ad not found")
    ad_doc["id"] = str(ad_doc["_id"])
    return RealEstateAd(**ad_doc)


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
    property_types = await db.real_estate_ads.aggregate([
        {"$group": {"_id": "$property_type", "count": {"$sum": 1}}}
    ]).to_list(None)
    
    # Price statistics
    price_stats = await db.real_estate_ads.aggregate([
        {"$match": {"price_amd": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": None,
            "avg_price": {"$avg": "$price_amd"},
            "min_price": {"$min": "$price_amd"},
            "max_price": {"$max": "$price_amd"}
        }}
    ]).to_list(None)
    
    # District distribution
    districts = await db.real_estate_ads.aggregate([
        {"$match": {"district": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$district", "count": {"$sum": 1}}}
    ]).to_list(None)
    
    return {
        "total_count": total_count,
        "property_types": property_types,
        "price_stats": price_stats[0] if price_stats else None,
        "districts": districts
    } 