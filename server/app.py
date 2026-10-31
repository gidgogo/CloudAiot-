"""FastAPI application wired to the v1 REST and WebSocket skeletons."""
from fastapi import FastAPI
from server.api import control_events, devices, health, help_requests, rooms, websocket
app=FastAPI(title="CloudAIoT API",version="1.0")
for router in (health.router, devices.router, rooms.router, control_events.router, help_requests.router, websocket.router):
    app.include_router(router)
