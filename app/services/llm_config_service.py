"""
Service for managing LLM configurations in database.
"""

import logging
from datetime import datetime, UTC
from typing import List, Optional
from bson import ObjectId

from app.db.mongodb import mongodb
from app.models.llm_config import LLMConfig
from app.services.encryption_service import encryption_service

logger = logging.getLogger(__name__)


class LLMConfigService:
    """Service for managing LLM configurations"""
    
    async def create_config(
        self,
        name: str,
        provider: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.1,
        created_by: Optional[int] = None,
    ) -> str:
        """Create a new LLM configuration"""
        try:
            # Encrypt API key
            encrypted_key = encryption_service.encrypt(api_key)
            
            # If this is the first config, make it active and default
            existing_configs = await self.get_all_configs()
            is_active = len(existing_configs) == 0
            is_default = len(existing_configs) == 0
            
            config_data = {
                "name": name,
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "encrypted_api_key": encrypted_key,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "is_active": is_active,
                "is_default": is_default,
                "created_by": created_by,
            }
            
            db = mongodb.get_database()
            result = await db.llm_configs.insert_one(config_data)
            
            logger.info("Created LLM config: %s (id: %s)", name, result.inserted_id)
            return str(result.inserted_id)
        except Exception as e:
            logger.error("Error creating LLM config: %s", e)
            raise
    
    async def get_all_configs(self, include_keys: bool = False) -> List[dict]:
        """Get all LLM configurations"""
        try:
            db = mongodb.get_database()
            configs = await db.llm_configs.find({}).sort("created_at", -1).to_list(length=None)
            
            result = []
            for config in configs:
                config_dict = {
                    "_id": str(config["_id"]),
                    "name": config.get("name"),
                    "provider": config.get("provider"),
                    "model": config.get("model"),
                    "base_url": config.get("base_url"),
                    "max_tokens": config.get("max_tokens", 1000),
                    "temperature": config.get("temperature", 0.1),
                    "is_active": config.get("is_active", False),
                    "is_default": config.get("is_default", False),
                    "created_at": config.get("created_at"),
                    "updated_at": config.get("updated_at"),
                    "created_by": config.get("created_by"),
                }
                
                # Only include decrypted key if requested
                if include_keys:
                    encrypted_key = config.get("encrypted_api_key", "")
                    if encrypted_key:
                        try:
                            config_dict["api_key"] = encryption_service.decrypt(encrypted_key)
                        except Exception as e:
                            logger.error("Error decrypting API key for config %s: %s", config["_id"], e)
                            config_dict["api_key"] = None
                    else:
                        config_dict["api_key"] = None
                else:
                    # Show masked key
                    encrypted_key = config.get("encrypted_api_key", "")
                    if encrypted_key:
                        config_dict["api_key"] = "***" + encrypted_key[-4:] if len(encrypted_key) > 4 else "***"
                    else:
                        config_dict["api_key"] = None
                
                result.append(config_dict)
            
            return result
        except Exception as e:
            logger.error("Error getting LLM configs: %s", e)
            raise
    
    async def get_config_by_id(self, config_id: str, include_key: bool = False) -> Optional[dict]:
        """Get LLM configuration by ID"""
        try:
            db = mongodb.get_database()
            config = await db.llm_configs.find_one({"_id": ObjectId(config_id)})
            
            if not config:
                return None
            
            config_dict = {
                "_id": str(config["_id"]),
                "name": config.get("name"),
                "provider": config.get("provider"),
                "model": config.get("model"),
                "base_url": config.get("base_url"),
                "max_tokens": config.get("max_tokens", 1000),
                "temperature": config.get("temperature", 0.1),
                "is_active": config.get("is_active", False),
                "is_default": config.get("is_default", False),
                "created_at": config.get("created_at"),
                "updated_at": config.get("updated_at"),
                "created_by": config.get("created_by"),
            }
            
            if include_key:
                encrypted_key = config.get("encrypted_api_key", "")
                if encrypted_key:
                    try:
                        config_dict["api_key"] = encryption_service.decrypt(encrypted_key)
                    except Exception as e:
                        logger.error("Error decrypting API key for config %s: %s", config_id, e)
                        config_dict["api_key"] = None
                else:
                    config_dict["api_key"] = None
            
            return config_dict
        except Exception as e:
            logger.error("Error getting LLM config by ID: %s", e)
            raise
    
    async def get_active_config(self, include_key: bool = True) -> Optional[dict]:
        """Get currently active LLM configuration"""
        try:
            db = mongodb.get_database()
            config = await db.llm_configs.find_one({"is_active": True})
            
            if not config:
                return None
            
            return await self.get_config_by_id(str(config["_id"]), include_key=include_key)
        except Exception as e:
            logger.error("Error getting active LLM config: %s", e)
            raise
    
    async def update_config(
        self,
        config_id: str,
        name: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> bool:
        """Update LLM configuration"""
        try:
            db = mongodb.get_database()
            update_data = {}
            
            if name is not None:
                update_data["name"] = name
            if provider is not None:
                update_data["provider"] = provider
            if model is not None:
                update_data["model"] = model
            if api_key is not None:
                update_data["encrypted_api_key"] = encryption_service.encrypt(api_key)
            if base_url is not None:
                update_data["base_url"] = base_url
            if max_tokens is not None:
                update_data["max_tokens"] = max_tokens
            if temperature is not None:
                update_data["temperature"] = temperature
            
            update_data["updated_at"] = datetime.now(UTC)
            
            result = await db.llm_configs.update_one(
                {"_id": ObjectId(config_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error("Error updating LLM config: %s", e)
            raise
    
    async def set_active_config(self, config_id: str) -> bool:
        """Set a configuration as active (deactivates all others)"""
        try:
            db = mongodb.get_database()
            
            # Deactivate all configs
            await db.llm_configs.update_many(
                {},
                {"$set": {"is_active": False}}
            )
            
            # Activate the selected config
            result = await db.llm_configs.update_one(
                {"_id": ObjectId(config_id)},
                {"$set": {"is_active": True, "updated_at": datetime.now(UTC)}}
            )
            
            return result.modified_count > 0
        except Exception as e:
            logger.error("Error setting active LLM config: %s", e)
            raise
    
    async def delete_config(self, config_id: str) -> bool:
        """Delete LLM configuration"""
        try:
            db = mongodb.get_database()
            
            # Check if this is the active config
            config = await db.llm_configs.find_one({"_id": ObjectId(config_id)})
            if config and config.get("is_active"):
                # Don't allow deleting active config
                raise ValueError("Cannot delete active configuration. Please activate another configuration first.")
            
            result = await db.llm_configs.delete_one({"_id": ObjectId(config_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error("Error deleting LLM config: %s", e)
            raise


# Singleton instance
llm_config_service = LLMConfigService()

