#!/usr/bin/env python3
"""
Script to restore user filters after data loss
"""

import asyncio
import httpx
import json
from typing import Dict, Any

API_BASE = "http://localhost:8001/api/v1"

async def restore_filters():
    """Restore filters for users"""
    
    # User filters to restore
    user_filters = {
        223720761: [  # Main user
            {
                "name": "3-4к",
                "description": "3-4 комнатные квартиры",
                "property_types": ["apartment"],
                "min_rooms": 3,
                "max_rooms": 6,
                "min_area": None,
                "max_area": None,
                "has_balcony": None,
                "has_air_conditioning": None,
                "has_internet": None,
                "has_furniture": None,
                "has_parking": None,
                "has_garden": None,
                "has_pool": None,
                "has_elevator": None,
                "pets_allowed": None,
                "utilities_included": None,
                "is_active": True
            }
        ],
        7497167557: [  # New user
            {
                "name": "2к",
                "description": "2-комнатные квартиры",
                "property_types": ["apartment"],
                "min_rooms": 2,
                "max_rooms": 2,
                "min_area": None,
                "max_area": None,
                "has_balcony": None,
                "has_air_conditioning": None,
                "has_internet": None,
                "has_furniture": None,
                "has_parking": None,
                "has_garden": None,
                "has_pool": None,
                "has_elevator": None,
                "pets_allowed": None,
                "utilities_included": None,
                "is_active": True
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        for user_id, filters in user_filters.items():
            print(f"🔄 Restoring filters for user {user_id}...")
            
            for filter_data in filters:
                try:
                    # Add user_id to filter data
                    filter_data["user_id"] = user_id
                    
                    response = await client.post(
                        f"{API_BASE}/simple-filters/",
                        json=filter_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"  ✅ Created filter: {filter_data['name']} (ID: {result['id']})")
                    else:
                        print(f"  ❌ Failed to create filter {filter_data['name']}: {response.text}")
                        
                except Exception as e:
                    print(f"  ❌ Error creating filter {filter_data['name']}: {e}")
    
    print("✅ Filter restoration completed!")

if __name__ == "__main__":
    asyncio.run(restore_filters())
