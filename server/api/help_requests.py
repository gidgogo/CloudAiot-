from fastapi import APIRouter
from shared.types import HelpRequest,HelpSource
router=APIRouter(prefix="/api/v1/help-requests",tags=["help"])
_requests:dict[str,HelpRequest]={}
@router.get("")
def list_help_requests(): return {"success":True,"data":[item.as_dict() for item in _requests.values()]}
@router.post("")
def create_help_request(payload:dict):
 request=HelpRequest(user_id=payload["user_id"],source=HelpSource.WEB); _requests[request.request_id]=request; return {"success":True,"data":request.as_dict()}
@router.patch("/{request_id}")
def update_help_request(request_id:str,payload:dict): return {"success":True,"data":{"request_id":request_id,**payload}}
