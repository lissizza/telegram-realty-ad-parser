from typing import List

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from app.models.search_settings import SearchSettings, SearchMode
from app.db.mongodb import mongodb

router = APIRouter()


@router.get("/", response_model=List[SearchSettings])
async def get_search_settings():
    """Get all search settings"""
    db = mongodb.get_database()
    settings = []
    async for setting_doc in db.search_settings.find():
        setting_doc["id"] = str(setting_doc["_id"])
        settings.append(SearchSettings(**setting_doc))
    return settings


@router.post("/", response_model=SearchSettings)
async def create_search_setting(setting_data: SearchSettings):
    """Create a new search setting"""
    db = mongodb.get_database()
    setting_dict = setting_data.dict(exclude={"id"})
    result = await db.search_settings.insert_one(setting_dict)
    setting_dict["id"] = str(result.inserted_id)
    return SearchSettings(**setting_dict)


@router.get("/{setting_id}", response_model=SearchSettings)
async def get_search_setting(setting_id: str):
    """Get a specific search setting"""
    db = mongodb.get_database()
    setting_doc = await db.search_settings.find_one({"_id": ObjectId(setting_id)})
    if not setting_doc:
        raise HTTPException(status_code=404, detail="Search setting not found")
    setting_doc["id"] = str(setting_doc["_id"])
    return SearchSettings(**setting_doc)


@router.put("/{setting_id}", response_model=SearchSettings)
async def update_search_setting(setting_id: str, setting_data: SearchSettings):
    """Update a search setting"""
    db = mongodb.get_database()
    setting_dict = setting_data.dict(exclude={"id"})
    result = await db.search_settings.update_one(
        {"_id": ObjectId(setting_id)}, {"$set": setting_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Search setting not found")
    setting_dict["id"] = setting_id
    return SearchSettings(**setting_dict)


@router.delete("/{setting_id}")
async def delete_search_setting(setting_id: str):
    """Delete a search setting"""
    db = mongodb.get_database()
    result = await db.search_settings.delete_one({"_id": ObjectId(setting_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Search setting not found")
    return {"message": "Search setting deleted successfully"}


@router.get("/active/", response_model=List[SearchSettings])
async def get_active_search_settings():
    """Get all active search settings"""
    db = mongodb.get_database()
    settings = []
    async for setting_doc in db.search_settings.find({"is_active": True}):
        setting_doc["id"] = str(setting_doc["_id"])
        settings.append(SearchSettings(**setting_doc))
    return settings


@router.post("/{setting_id}/activate")
async def activate_search_setting(setting_id: str):
    """Activate a search setting"""
    db = mongodb.get_database()
    result = await db.search_settings.update_one(
        {"_id": ObjectId(setting_id)}, {"$set": {"is_active": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Search setting not found")
    return {"message": "Search setting activated"}


@router.post("/{setting_id}/deactivate")
async def deactivate_search_setting(setting_id: str):
    """Deactivate a search setting"""
    db = mongodb.get_database()
    result = await db.search_settings.update_one(
        {"_id": ObjectId(setting_id)}, {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Search setting not found")
    return {"message": "Search setting deactivated"}


@router.post("/{setting_id}/test")
async def test_search_setting(setting_id: str, test_text: str):
    """Test a search setting with sample text"""
    db = mongodb.get_database()
    setting_doc = await db.search_settings.find_one({"_id": ObjectId(setting_id)})
    if not setting_doc:
        raise HTTPException(status_code=404, detail="Search setting not found")
    
    setting = SearchSettings(**setting_doc)
    
    # Generate prompt and return it (for testing)
    prompt = setting.get_llm_prompt()
    
    return {
        "setting_name": setting.name,
        "mode": setting.mode,
        "prompt": prompt,
        "test_text": test_text
    }

