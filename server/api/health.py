from fastapi import APIRouter
router=APIRouter(tags=["health"])
@router.get("/health")
def health(): return {"success":True,"data":{"status":"ok"}}
