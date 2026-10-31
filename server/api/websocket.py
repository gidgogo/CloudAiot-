from fastapi import APIRouter,WebSocket
router=APIRouter()
@router.websocket("/ws/v1/events")
async def event_socket(websocket:WebSocket):
 await websocket.accept()
 try:
  while True: await websocket.receive_text()
 except Exception: await websocket.close()
