"""Publishes JobDiscoveredEvents to a RabbitMQ topic exchange."""

from __future__ import annotations

import logging
from typing import Protocol

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from app.models import JobDiscoveredEvent

log = logging.getLogger(__name__)

EXCHANGE = "jobs.events"
ROUTING_KEY = "job.discovered"


class Publisher(Protocol):
    async def publish(self, event: JobDiscoveredEvent) -> None: ...
    async def close(self) -> None: ...
    def is_connected(self) -> bool: ...


class RabbitPublisher:
    """Durable exchange + persistent messages + publisher confirms + mandatory routing.

    The scraper only knows about the exchange; queues are owned by consumers, so new
    services can subscribe to job events without any change here.

    Messages are published as mandatory with on_return_raises=True: if no consumer queue is
    bound yet (e.g. the tracker hasn't started), the broker returns the message and publish()
    raises, so the scraper rolls back its dedup mark and retries next sweep instead of the
    posting being silently dropped.
    """

    def __init__(self, url: str):
        self._url = url
        self._conn: AbstractRobustConnection | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self._conn = await aio_pika.connect_robust(self._url)
        channel = await self._conn.channel(publisher_confirms=True, on_return_raises=True)
        self._exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        log.info("connected to RabbitMQ, exchange=%s", EXCHANGE)

    async def publish(self, event: JobDiscoveredEvent) -> None:
        if self._exchange is None:
            raise RuntimeError("publisher not connected")
        await self._exchange.publish(
            aio_pika.Message(
                body=event.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=event.eventId,
                type=event.eventType,
            ),
            routing_key=ROUTING_KEY,
            mandatory=True,
        )

    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()


class InMemoryPublisher:
    def __init__(self) -> None:
        self.events: list[JobDiscoveredEvent] = []
        self.fail_next = False

    async def publish(self, event: JobDiscoveredEvent) -> None:
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("broker unavailable")
        self.events.append(event)

    async def close(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True
