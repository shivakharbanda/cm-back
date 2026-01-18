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
        """
        async with async_session_maker() as session:
            try:
                processor = CommentProcessor(session)
                result = await processor.process(payload)
                await session.commit()
                return result
            except Exception as e:
                logger.error(f"Error processing comment: {e}", exc_info=True)
                await session.rollback()
                return False

    async def run(self) -> None:
        """Run the worker process."""
        logger.info("Starting automation worker...")

        # Setup signal handlers for graceful shutdown (Unix only)
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._handle_shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            logger.info("Signal handlers not supported on this platform")

        try:
            # Connect to RabbitMQ
            await rabbitmq_consumer.connect()

            # Start consuming comments
            logger.info(f"Consuming from queue: {COMMENTS_QUEUE}")

            # Run consumer until shutdown
            consume_task = asyncio.create_task(
                rabbitmq_consumer.consume(
                    queue_name=COMMENTS_QUEUE,
                    callback=self.process_comment,
                )
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

            # Cancel consume task
            consume_task.cancel()
            try:
                await consume_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            raise

        finally:
            await rabbitmq_consumer.disconnect()
            logger.info("Worker stopped")

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
