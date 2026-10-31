"""Device API contract skeleton; replace the memory store with DeviceRepository."""
from fastapi import APIRouter
router=APIRouter(prefix="/api/v1/devices",tags=["devices"])
_devices:dict[str,dict]={}
@router.get("")
def list_devices(): return {"success":True,"data":list(_devices.values())}
@router.post("")
def create_device(device:dict): _devices[device["device_id"]]=device; return {"success":True,"data":device}
@router.patch("/{device_id}")
def update_device(device_id:str,changes:dict): _devices[device_id].update(changes); return {"success":True,"data":_devices[device_id]}
