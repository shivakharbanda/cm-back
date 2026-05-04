"""Worker process for consuming RabbitMQ messages and processing automations.

Run with: python -m app.worker
"""

import asyncio
import logging
import signal
import sys
from typing import Any

from app.config import settings
from app.db import async_session_maker
from app.services.comment_processor import CommentProcessor
from app.services.email.dispatcher import EmailDispatcher
from app.services.rabbitmq_consumer import rabbitmq_consumer

# Queue names - these are defined by the webhook service
COMMENTS_QUEUE = "instagram.comments"

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class Worker:
    """Worker process that consumes comment events and processes automations."""

    def __init__(self):
        self._shutdown_event = asyncio.Event()

    async def process_comment(self, payload: dict[str, Any]) -> bool:
        """Process a single comment event.

        This is called for each message consumed from RabbitMQ.
        CommentProcessor owns commit/rollback — it commits mid-flow so the
        'pending' DMSentLog row lands before the Graph API side effect.
        """
        async with async_session_maker() as session:
            try:
                processor = CommentProcessor(session)
                return await processor.process(payload)
            except Exception as e:
                logger.error(f"Error processing comment: {e}", exc_info=True)
                await session.rollback()
                return False

    async def run(self) -> None:
        """Run the worker process."""
        logger.info("Starting automation worker...")

        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._handle_shutdown)
        except NotImplementedError:
            logger.info("Signal handlers not supported on this platform")

        # Email dispatcher only needs Postgres — start it before any RabbitMQ work.
        # RabbitMQ consumer runs in its own retry loop; its failures don't touch email.
        dispatch_task = asyncio.create_task(
            EmailDispatcher(shutdown_event=self._shutdown_event).run()
        )
        consume_task = asyncio.create_task(self._run_rabbitmq_with_retry())

        try:
            await self._shutdown_event.wait()
        finally:
            for task in (consume_task, dispatch_task):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await rabbitmq_consumer.disconnect()
            logger.info("Worker stopped")

    async def _run_rabbitmq_with_retry(self) -> None:
        """Connect to RabbitMQ and consume messages, retrying on any failure."""
        while not self._shutdown_event.is_set():
            try:
                await rabbitmq_consumer.connect()
                logger.info(f"Connected to RabbitMQ. Consuming from queue: {COMMENTS_QUEUE}")
                await rabbitmq_consumer.consume(
                    queue_name=COMMENTS_QUEUE,
                    callback=self.process_comment,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._shutdown_event.is_set():
                    return
                logger.error(f"RabbitMQ error: {e}. Retrying in 10 seconds...")
                try:
                    await rabbitmq_consumer.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(10)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping worker...")
        self._shutdown_event.set()


async def main() -> None:
    """Main entry point for the worker."""
    worker = Worker()
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)
