"""RabbitMQ consumer service for processing Instagram webhook events."""

import json
import logging
from typing import Callable, Awaitable

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel

from app.config import settings

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """RabbitMQ consumer with robust connection handling."""

    def __init__(self):
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._is_running = False

    async def connect(self) -> None:
        """Establish connection to RabbitMQ with automatic reconnection."""
        logger.info(f"Connecting to RabbitMQ...")

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

        # Get the queue (it should already exist, created by webhook service)
        queue = await self._channel.get_queue(queue_name, ensure=False)

        logger.info(f"Starting to consume from queue: {queue_name}")
        self._is_running = True

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._is_running:
                    break

                await self._process_message(message, callback)

    async def _process_message(
        self,
        message: IncomingMessage,
        callback: Callable[[dict], Awaitable[bool]],
    ) -> None:
        """Process a single message with error handling."""
        try:
            body = message.body.decode("utf-8")
            payload = json.loads(body)

            logger.debug(f"Received message: {message.message_id}")

            success = await callback(payload)

            if success:
                await message.ack()
                logger.debug(f"Message {message.message_id} acknowledged")
            else:
                await message.nack(requeue=True)
                logger.warning(f"Message {message.message_id} nacked for retry")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message as JSON: {e}")
            await message.ack()

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
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
