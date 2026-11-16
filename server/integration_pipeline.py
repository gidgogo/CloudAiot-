"""Connect Vision, Intent, web services and MQTT for one Edge camera stream."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from server.db.session import Database
from server.intent.engine import IntentEngine
from server.services.device_service import DeviceService, GestureMappingService
from server.services.help_service import HelpService
from server.vision.landmark_processor import oriented_frame_size
from server.vision.pipeline import GesturePipeline
from shared.types import FrameMetadata, GestureResult, IntentAction, IntentResult, IntentStatus

log = logging.getLogger(__name__)


class CommandPublisher(Protocol):
    def publish_intent(self, intent: IntentResult) -> None: ...


class IntentDispatcher:
    """Apply meaningful intent results to web, help and device-control paths."""

    def __init__(self, db: Database, events, command_publisher: CommandPublisher | None) -> None:
        self.db = db
        self.events = events
        self.command_publisher = command_publisher

    def dispatch(self, intent: IntentResult) -> None:
        if intent.status is IntentStatus.PENDING:
            if intent.target_device_id:
                with self.db.session() as session:
                    device = DeviceService(session).get(intent.target_device_id, intent.correlation_id)
                self.events.publish(
                    "device.selected",
                    {"device_id": intent.target_device_id, "device_name": device.name},
                    correlation_id=intent.correlation_id,
                )
            return
        if intent.status is IntentStatus.CANCELLED:
            log.info(
                "intent cancelled correlation_id=%s reason=%s",
                intent.correlation_id,
                intent.cancel_reason,
            )
            return

        self.events.publish(
            "gesture.confirmed",
            {
                "action": intent.action.value if intent.action else None,
                "target_device_id": intent.target_device_id,
            },
            correlation_id=intent.correlation_id,
        )
        if intent.action is IntentAction.HELP:
            with self.db.session() as session:
                HelpService(session, self.events).create_from_gesture(intent.correlation_id)
            return
        if intent.action in (IntentAction.ON, IntentAction.OFF):
            if self.command_publisher is None:
                raise RuntimeError("MQTT is disabled; confirmed device intent cannot be published")
            self.command_publisher.publish_intent(intent)


class FrameSessionProcessor:
    """Stateful Vision→Intent processor. Create one instance per Edge WebSocket."""

    def __init__(
        self,
        db: Database,
        dispatcher: IntentDispatcher,
        *,
        gesture_pipeline: GesturePipeline | None = None,
        intent_engine: IntentEngine | None = None,
    ) -> None:
        self.db = db
        self.dispatcher = dispatcher
        self.gestures = gesture_pipeline or GesturePipeline()
        self._actions: dict = {}
        self.intent = intent_engine or IntentEngine(action_for=self._actions.get)

    def process(self, jpeg: bytes, metadata: FrameMetadata) -> tuple[GestureResult, IntentResult | None]:
        gesture = self.gestures.process_jpeg(jpeg, metadata)
        with self.db.session() as session:
            self.intent.update_regions(DeviceService(session).pointing_regions())
            self._actions.clear()
            self._actions.update(
                (mapping.gesture, IntentAction(mapping.action))
                for mapping in GestureMappingService(session).list()
                if mapping.enabled
            )
        width, height = oriented_frame_size(metadata.width, metadata.height, metadata.rotation_deg)
        intent = self.intent.consume(gesture, frame_width=width, frame_height=height)
        if intent is not None:
            self.dispatcher.dispatch(intent)
        return gesture, intent

    def tick(self) -> IntentResult | None:
        """Expire a pending selection even when the Edge stream stops producing frames."""
        intent = self.intent.tick()
        if intent is not None:
            self.dispatcher.dispatch(intent)
        return intent

    def close(self) -> None:
        self.gestures.close()
