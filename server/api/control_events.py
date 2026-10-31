from fastapi import APIRouter
router=APIRouter(prefix="/api/v1/control-events",tags=["control-events"])
@router.get("")
def list_control_events(): return {"success":True,"data":[]}
