import asyncio
import json
from fastapi import WebSocket
from redis.asyncio import Redis
from app.core.config import settings


class ScheduleWebSocketManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.redis: Redis | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        for conn in self.connections:
            try:
                await conn.send_text(payload)
            except Exception:
                self.disconnect(conn)

    async def start_redis_listener(self):
        self.redis = Redis.from_url(settings.redis_url)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("schedule_updates")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    await self.broadcast(data)
                except Exception:
                    pass


manager = ScheduleWebSocketManager()
