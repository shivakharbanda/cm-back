"""RabbitMQ consumer service for processing Instagram webhook events."""

import asyncio
import json
import logging
from collections import OrderedDict
from typing import Awaitable, Callable

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from aio_pika.exceptions import ChannelClosed

from app.config import settings

logger = logging.getLogger(__name__)


# Maximum times the same envelope id may be redelivered before we drop it.
# Keyed by WebhookMessage.id (set by the webhook service) — stable across
# redeliveries. Counter is in-process, so worker restart resets it; that's
# acceptable because workers rarely restart and the permanent-failure ack
# path handles most real poison cases without ever hitting this cap.
MAX_DELIVERIES = 3
DELIVERY_COUNTER_MAX_ENTRIES = 10_000

# Cold-boot retry when the publisher hasn't declared the queue yet.
QUEUE_LOOKUP_RETRIES = 3
QUEUE_LOOKUP_BACKOFF_SECONDS = 2.0


class RabbitMQConsumer:
    """RabbitMQ consumer with robust connection handling."""

    def __init__(self):
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._is_running = False
        # LRU of envelope_id -> delivery count.
        self._delivery_counts: OrderedDict[str, int] = OrderedDict()

    async def connect(self) -> None:
        """Establish connection to RabbitMQ with automatic reconnection."""
        logger.info("Connecting to RabbitMQ...")

        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        logger.info("Successfully connected to RabbitMQ")

    async def disconnect(self) -> None:
        """Gracefully close RabbitMQ connection."""
        self._is_running = False

        if self._channel:
            await self._channel.close()
            self._channel = None

        if self._connection:
            await self._connection.close()
            self._connection = None

        logger.info("Disconnected from RabbitMQ")

    async def consume(
        self,
        queue_name: str,
        callback: Callable[[dict], Awaitable[bool]],
    ) -> None:
        """Start consuming messages from a queue.

        Args:
            queue_name: Name of the queue to consume from
            callback: Async function to process each message.
                      Should return True on success, False on failure.
        """
        if not self._channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        queue = await self._get_queue_with_retry(queue_name)

        logger.info(f"Starting to consume from queue: {queue_name}")
        self._is_running = True

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._is_running:
                    break

                await self._process_message(message, callback)

    async def _get_queue_with_retry(self, queue_name: str):
        """Look up a queue declared by the webhook service.

        If the webhook service hasn't started yet (cold boot), the queue won't
        exist. Retry a few times with backoff before giving up, so the worker
        doesn't crash-loop when co-deployed with the webhook service.
        """
        assert self._channel is not None
        last_err: Exception | None = None
        for attempt in range(1, QUEUE_LOOKUP_RETRIES + 1):
            try:
                return await self._channel.get_queue(queue_name, ensure=False)
            except ChannelClosed as e:
                last_err = e
                logger.warning(
                    f"Queue '{queue_name}' not found on attempt {attempt}/"
                    f"{QUEUE_LOOKUP_RETRIES}. Is the webhook service running? "
                    f"Retrying in {QUEUE_LOOKUP_BACKOFF_SECONDS}s..."
                )
                # Channel is dead after NOT_FOUND — re-open before retrying.
                if self._connection:
                    self._channel = await self._connection.channel()
                    await self._channel.set_qos(prefetch_count=10)
                await asyncio.sleep(QUEUE_LOOKUP_BACKOFF_SECONDS)
        raise RuntimeError(
            f"Queue '{queue_name}' does not exist after "
            f"{QUEUE_LOOKUP_RETRIES} attempts. The webhook service declares "
            f"queues on startup — start it first."
        ) from last_err

    def _bump_delivery_count(self, envelope_id: str | None) -> int:
        """Increment and return the in-process delivery count for an envelope id.

        Returns 1 on the first observation.
        """
        if not envelope_id:
            # No stable id — can't count. Caller must treat as first delivery.
            return 1
        count = self._delivery_counts.get(envelope_id, 0) + 1
        self._delivery_counts[envelope_id] = count
        # LRU: move to end so oldest falls off first.
        self._delivery_counts.move_to_end(envelope_id)
        while len(self._delivery_counts) > DELIVERY_COUNTER_MAX_ENTRIES:
            self._delivery_counts.popitem(last=False)
        return count

    def _clear_delivery_count(self, envelope_id: str | None) -> None:
        if envelope_id:
            self._delivery_counts.pop(envelope_id, None)

    async def _process_message(
        self,
        message: IncomingMessage,
        callback: Callable[[dict], Awaitable[bool]],
    ) -> None:
        """Process a single message with error handling and a redelivery cap."""
        envelope_id: str | None = None
        try:
            body = message.body.decode("utf-8")
            payload = json.loads(body)
            envelope_id = payload.get("id") if isinstance(payload, dict) else None

            delivery_num = self._bump_delivery_count(envelope_id)
            if delivery_num > MAX_DELIVERIES:
                logger.error(
                    "Dropping message after exceeding delivery cap "
                    f"envelope_id={envelope_id} delivery_num={delivery_num} "
                    f"max={MAX_DELIVERIES} account_id={payload.get('account_id')} "
                    f"event_type={payload.get('event_type')}"
                )
                await message.nack(requeue=False)
                self._clear_delivery_count(envelope_id)
                return

            logger.debug(
                f"Received message envelope_id={envelope_id} "
                f"delivery_num={delivery_num}"
            )

            success = await callback(payload)

            if success:
                await message.ack()
                self._clear_delivery_count(envelope_id)
                logger.debug(f"Message {envelope_id} acknowledged")
            else:
                await message.nack(requeue=True)
                logger.warning(
                    f"Message {envelope_id} nacked (delivery {delivery_num}/"
                    f"{MAX_DELIVERIES})"
                )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message as JSON: {e}")
            await message.ack()

        except Exception as e:
            logger.error(
                f"Error processing message envelope_id={envelope_id}: {e}",
                exc_info=True,
            )
            await message.nack(requeue=True)

    @property
    def is_connected(self) -> bool:
        """Check if consumer is connected to RabbitMQ."""
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._channel is not None
            and not self._channel.is_closed
        )


rabbitmq_consumer = RabbitMQConsumer()
