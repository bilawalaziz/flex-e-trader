import json
import logging
from fastapi import WebSocket
from redis.asyncio import Redis
from app.core.config import settings
from app.core.metrics import websocket_broadcasts_total, websocket_connections

logger = logging.getLogger(__name__)


class ScheduleWebSocketManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.redis: Redis | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        websocket_connections.set(len(self.connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
            websocket_connections.set(len(self.connections))

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        # Iterate a copy: a failed send disconnects the client, and mutating
        # the list being iterated skips the next one.
        for conn in list(self.connections):
            try:
                await conn.send_text(payload)
                websocket_broadcasts_total.labels(outcome="sent").inc()
            except Exception:
                websocket_broadcasts_total.labels(outcome="dropped").inc()
                self.disconnect(conn)

    async def start_redis_listener(self):
        self.redis = Redis.from_url(settings.redis_url)
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("schedule_updates")
        logger.info("redis listener subscribed | channel=schedule_updates")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    await self.broadcast(data)
                except Exception:
                    logger.exception("failed to broadcast schedule update")


manager = ScheduleWebSocketManager()
