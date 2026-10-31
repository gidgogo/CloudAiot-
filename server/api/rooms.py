from fastapi import APIRouter
router=APIRouter(prefix="/api/v1/rooms",tags=["rooms"])
_rooms:dict[str,dict]={}
@router.get("")
def list_rooms(): return {"success":True,"data":list(_rooms.values())}
@router.post("")
def create_room(room:dict): _rooms[room["room_id"]]=room; return {"success":True,"data":room}
