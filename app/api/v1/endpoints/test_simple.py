from fastapi import APIRouter

router = APIRouter()

@router.post("/test-simple")
async def test_simple_endpoint():
    """Simple test endpoint"""
    return {"message": "Simple test works"}
