"""In-process event bus for live workspace updates.

Powers the WebSocket fan-out: every background job progress tick, activity,
notification, and version event is published to a channel and delivered to all
connected clients for that project/user. Swappable for a Redis pub/sub later
without changing callers.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any


class EventBus:
    """Async pub/sub with per-channel subscriber queues."""

    def __init__(self) -> None:
        self._channels: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    def subscribe(self, channel: str) -> asyncio.Queue[str]:
        """Register a subscriber queue for a channel."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
        self._channels[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[str]) -> None:
        """Remove a subscriber queue."""
        self._channels.get(channel, set()).discard(queue)
        if channel in self._channels and not self._channels[channel]:
            del self._channels[channel]

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Serialize and enqueue an event for every subscriber (best effort)."""
        payload = json.dumps(event, default=str)
        async with self._lock:
            subscribers = list(self._channels.get(channel, ()))
        for queue in subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop oldest event so the client never falls behind on progress.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    pass


bus = EventBus()


def _event(event_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "type": event_type,
        "payload": payload or {},
        "ts": datetime.now(UTC).isoformat(),
    }


def publish_project_event(project_id: str | Any, event_type: str, payload: dict[str, Any] | None = None) -> None:
    """Fire-and-forget publish to a project channel (safe when no loop is running)."""
    event = _event(event_type, payload)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    asyncio.create_task(bus.publish(f"project:{project_id}", event))


def publish_user_event(user_id: str | Any, event_type: str, payload: dict[str, Any] | None = None) -> None:
    """Fire-and-forget publish to a user channel."""
    event = _event(event_type, payload)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    asyncio.create_task(bus.publish(f"user:{user_id}", event))
