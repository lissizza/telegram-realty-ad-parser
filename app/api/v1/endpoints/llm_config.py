"""
API endpoints for managing LLM configurations.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from app.bot.admin_decorators import is_super_admin
from app.services.llm_config_service import llm_config_service

router = APIRouter()


class LLMConfigCreate(BaseModel):
    """Request model for creating LLM configuration"""
    name: str = Field(..., description="Display name for this LLM configuration")
    provider: str = Field(..., description="Provider type: openai, anthropic, zai, local, mock")
    model: str = Field(..., description="Model name")
    api_key: str = Field(..., description="API key (will be encrypted)")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    max_tokens: int = Field(default=1000, description="Maximum tokens")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="Temperature")


class LLMConfigUpdate(BaseModel):
    """Request model for updating LLM configuration"""
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)


class LLMConfigResponse(BaseModel):
    """Response model for LLM configuration"""
    _id: str
    name: str
    provider: str
    model: str
    base_url: Optional[str]
    api_key: Optional[str]  # Masked or decrypted based on include_key
    max_tokens: int
    temperature: float
    is_active: bool
    is_default: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    created_by: Optional[int]


@router.get("/llm-configs", response_model=List[LLMConfigResponse])
async def get_llm_configs(
    user_id: int = Query(..., description="User ID"),
    include_keys: bool = Query(False, description="Include decrypted API keys (super admin only)")
):
    """Get all LLM configurations (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        configs = await llm_config_service.get_all_configs(include_keys=include_keys)
        return configs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-configs/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    config_id: str,
    user_id: int = Query(..., description="User ID"),
    include_key: bool = Query(False, description="Include decrypted API key (super admin only)")
):
    """Get LLM configuration by ID (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        config = await llm_config_service.get_config_by_id(config_id, include_key=include_key)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-configs/active", response_model=LLMConfigResponse)
async def get_active_llm_config(
    user_id: int = Query(..., description="User ID"),
    include_key: bool = Query(False, description="Include decrypted API key (super admin only)")
):
    """Get currently active LLM configuration (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        config = await llm_config_service.get_active_config(include_key=include_key)
        if not config:
            raise HTTPException(status_code=404, detail="No active configuration found")
        
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm-configs", response_model=dict)
async def create_llm_config(
    config_data: LLMConfigCreate,
    user_id: int = Query(..., description="User ID")
):
    """Create new LLM configuration (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        config_id = await llm_config_service.create_config(
            name=config_data.name,
            provider=config_data.provider,
            model=config_data.model,
            api_key=config_data.api_key,
            base_url=config_data.base_url,
            max_tokens=config_data.max_tokens,
            temperature=config_data.temperature,
            created_by=user_id,
        )
        
        return {"config_id": config_id, "message": "Configuration created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/llm-configs/{config_id}", response_model=dict)
async def update_llm_config(
    config_id: str,
    config_data: LLMConfigUpdate,
    user_id: int = Query(..., description="User ID")
):
    """Update LLM configuration (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        success = await llm_config_service.update_config(
            config_id=config_id,
            name=config_data.name,
            provider=config_data.provider,
            model=config_data.model,
            api_key=config_data.api_key,
            base_url=config_data.base_url,
            max_tokens=config_data.max_tokens,
            temperature=config_data.temperature,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm-configs/{config_id}/activate", response_model=dict)
async def activate_llm_config(
    config_id: str,
    user_id: int = Query(..., description="User ID")
):
    """Activate LLM configuration (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        success = await llm_config_service.set_active_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        return {"message": "Configuration activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/llm-configs/{config_id}", response_model=dict)
async def delete_llm_config(
    config_id: str,
    user_id: int = Query(..., description="User ID")
):
    """Delete LLM configuration (super admin only)"""
    try:
        if not await is_super_admin(user_id):
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        success = await llm_config_service.delete_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        return {"message": "Configuration deleted successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





