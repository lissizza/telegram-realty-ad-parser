#!/usr/bin/env python3
"""
Script to check and clean up test filters from the database
"""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append('/app')
os.chdir('/app')

from app.db.mongodb import mongodb

async def check_and_clean_filters():
    """Check and clean up test filters"""
    try:
        db = mongodb.get_database()
        
        # Get all filters
        all_filters = await db.simple_filters.find({}).to_list(length=None)
        print(f"Total filters in database: {len(all_filters)}")
        
        # Find test filters
        test_filters = []
        for filter_doc in all_filters:
            name = filter_doc.get("name", "")
            if "Test" in name or "test" in name:
                test_filters.append(filter_doc)
                print(f"Found test filter: {name} (ID: {filter_doc['_id']}, user_id: {filter_doc.get('user_id')})")
        
        # Find filters with min_rooms=2, max_rooms=3
        room_filters = await db.simple_filters.find({
            "min_rooms": 2, 
            "max_rooms": 3
        }).to_list(length=None)
        
        print(f"\nFilters with 2-3 rooms: {len(room_filters)}")
        for filter_doc in room_filters:
            print(f"  - {filter_doc['name']}: user_id={filter_doc.get('user_id')}, active={filter_doc.get('is_active', False)}")
        
        # Find filters for user 223720761
        user_filters = await db.simple_filters.find({"user_id": 223720761}).to_list(length=None)
        print(f"\nFilters for user 223720761: {len(user_filters)}")
        for filter_doc in user_filters:
            print(f"  - {filter_doc['name']}: {filter_doc.get('min_rooms', 'None')}-{filter_doc.get('max_rooms', 'None')} rooms, active={filter_doc.get('is_active', False)}")
        
        # Find filters with invalid ObjectId
        invalid_filters = await db.simple_filters.find({
            "_id": {"$regex": "unknown|test|invalid"}
        }).to_list(length=None)
        
        print(f"\nFilters with invalid IDs: {len(invalid_filters)}")
        for filter_doc in invalid_filters:
            print(f"  - {filter_doc['name']}: ID={filter_doc['_id']}")
        
        return test_filters, room_filters, invalid_filters
        
    except Exception as e:
        print(f"Error: {e}")
        return [], [], []

if __name__ == "__main__":
    asyncio.run(check_and_clean_filters())
