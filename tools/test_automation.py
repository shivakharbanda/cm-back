#!/usr/bin/env python3
"""Test automation processing with real Instagram comments.

Fetches real comments from the Instagram API and feeds them through the
production CommentProcessor, bypassing the webhook and RabbitMQ entirely.
This reuses the exact production code path: parsing, automation matching,
deduplication, DM sending, comment replying, and logging.

Usage (from cm-back directory):
    uv run python tools/test_automation.py                    # Process all posts
    uv run python tools/test_automation.py --post-id <id>     # Target a specific post
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import psycopg
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Ensure the cm-back directory is on sys.path so `app` package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

GRAPH_API_URL = os.getenv("INSTAGRAM_GRAPH_API_URL", "https://graph.instagram.com")

# Custom formatter to mute log output color
class MutedColorFormatter(logging.Formatter):
    GREY = "\x1b[90m"  # ANSI escape code for bright black (grey)
    RESET = "\x1b[0m"

    def format(self, record):
        message = super().format(record)
        return f"{self.GREY}{message}{self.RESET}"


# Suppress SQLAlchemy's noisy SQL query logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

# Configure logging to see CommentProcessor output with muted colors
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
formatter = MutedColorFormatter(
    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)

if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(handler)
logger = logging.getLogger(__name__)


def get_instagram_account() -> dict:
    """Fetch the first instagram account from the database."""
    conn = psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        dbname=os.getenv("DB_NAME", "automation_db"),
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT instagram_user_id, username, access_token "
                "FROM instagram_accounts LIMIT 1"
            )
            row = cur.fetchone()
    conn.close()

    if not row:
        print("ERROR: No Instagram account found in the database.")
        sys.exit(1)

    return {
        "instagram_user_id": row[0],
        "username": row[1],
        "access_token": row[2],
    }


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt the access token using ENCRYPTION_KEY from .env."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        print("ERROR: ENCRYPTION_KEY not found in environment.")
        sys.exit(1)
    cipher = Fernet(key.encode())
    return cipher.decrypt(encrypted_token.encode()).decode()


def fetch_posts(access_token: str, user_id: str) -> list[dict]:
    """Fetch the user's Instagram posts."""
    resp = httpx.get(
        f"{GRAPH_API_URL}/{user_id}/media",
        params={
            "fields": "id,caption,media_type,permalink,timestamp",
            "access_token": access_token,
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_comments(access_token: str, media_id: str) -> list[dict]:
    """Fetch comments on a specific post."""
    resp = httpx.get(
        f"{GRAPH_API_URL}/{media_id}/comments",
        params={
            "fields": "id,text,username,from,timestamp",
            "access_token": access_token,
        },
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def build_webhook_payload(
    account_id: str,
    comment: dict,
    media_id: str,
    media_type: str,
) -> dict:
    """Construct a webhook-formatted payload dict for CommentProcessor.

    Matches the format that CommentEvent.from_webhook_payload() expects.
    """
    from_data = comment.get("from", {})
    comment_timestamp = comment.get("timestamp", "")

    # Parse the Instagram timestamp to a unix timestamp
    try:
        dt = datetime.fromisoformat(comment_timestamp.replace("Z", "+00:00"))
        unix_ts = int(dt.timestamp())
    except (ValueError, AttributeError):
        dt = datetime.now(timezone.utc)
        unix_ts = int(dt.timestamp())

    return {
        "id": str(uuid4()),
        "timestamp": dt.isoformat(),
        "source": "instagram",
        "event_type": "comments",
        "account_id": account_id,
        "raw_payload": {
            "id": account_id,
            "time": unix_ts,
            "changes": [
                {
                    "value": {
                        "from": {
                            "id": from_data.get("id", ""),
                            "username": from_data.get("username", comment.get("username", "")),
                        },
                        "media": {
                            "id": media_id,
                            "media_product_type": media_type,
                        },
                        "id": comment.get("id", ""),
                        "text": comment.get("text", ""),
                    },
                    "field": "comments",
                }
            ],
        },
    }


async def process_comments(payloads: list[dict]) -> dict:
    """Process all comment payloads through the production CommentProcessor.

    Returns a summary dict with counts and per-comment results.
    """
    from app.db import async_session_maker
    from app.models import DMSentLog, Automation
    from app.services.comment_processor import CommentProcessor
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    processed = 0
    errors = 0
    dms_sent = 0
    dms_failed = 0
    dms_deduped = 0
    no_automation = 0

    for payload in payloads:
        value = payload["raw_payload"]["changes"][0]["value"]
        comment_text = value.get("text", "")
        commenter = value["from"].get("username", "unknown")
        commenter_id = value["from"].get("id", "")
        comment_id = value.get("id", "unknown")
        media_id = value["media"].get("id", "")

        print(f"\n  Processing comment {comment_id} by @{commenter}: \"{comment_text}\"")

        async with async_session_maker() as session:
            try:
                # Check dm_sent_log before processing to detect new entries afterward
                pre_count_result = await session.execute(
                    select(DMSentLog).where(
                        DMSentLog.comment_id == comment_id,
                    )
                )
                pre_existing = {row.id for row in pre_count_result.scalars().all()}

                # Also check if any automation exists for this post
                auto_result = await session.execute(
                    select(Automation)
                    .options(joinedload(Automation.instagram_account))
                    .where(
                        Automation.post_id == media_id,
                        Automation.is_active == True,  # noqa: E712
                    )
                )
                automations = list(auto_result.scalars().unique().all())
                if automations:
                    for auto in automations:
                        print(f"    Automation: \"{auto.name}\" | type={auto.message_type.value} | trigger={auto.trigger_type.value}")
                else:
                    print(f"    (no active automations for this post)")
                    no_automation += 1

                # Check if already deduped for each automation
                already_sent_all = True
                for auto in automations:
                    dedup_result = await session.execute(
                        select(DMSentLog).where(
                            DMSentLog.automation_id == auto.id,
                            DMSentLog.post_id == media_id,
                            DMSentLog.commenter_user_id == commenter_id,
                            DMSentLog.comment_id == comment_id,
                            DMSentLog.status == "sent",
                        )
                    )
                    if dedup_result.first() is None:
                        already_sent_all = False

                processor = CommentProcessor(session)
                await processor.process(payload)
                await session.commit()
                processed += 1

                if not automations:
                    continue

                if already_sent_all and automations:
                    print(f"    -> SKIPPED (DM already sent — deduplication)")
                    dms_deduped += 1
                    continue

                # Check dm_sent_log after processing to see what happened
                post_count_result = await session.execute(
                    select(DMSentLog).where(
                        DMSentLog.comment_id == comment_id,
                    )
                )
                all_entries = post_count_result.scalars().all()
                new_entries = [e for e in all_entries if e.id not in pre_existing]

                for entry in new_entries:
                    if entry.status == "sent":
                        print(f"    -> DM SENT to @{commenter}")
                        dms_sent += 1
                    else:
                        print(f"    -> DM FAILED (status={entry.status})")
                        dms_failed += 1

                if not new_entries and automations:
                    print(f"    -> NO DM (trigger condition not met)")

            except Exception as e:
                await session.rollback()
                errors += 1
                processed += 1
                print(f"    -> ERROR: {e}")
                logger.error(f"Error processing comment: {e}", exc_info=True)

    return {
        "processed": processed,
        "dms_sent": dms_sent,
        "dms_failed": dms_failed,
        "dms_deduped": dms_deduped,
        "no_automation": no_automation,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test automation processing with real Instagram comments."
    )
    parser.add_argument(
        "--post-id",
        "-p",
        default=None,
        help="Limit to a specific Instagram media ID. If omitted, scans all posts.",
    )
    args = parser.parse_args()

    # 1. Get account from DB
    print("Connecting to database...")
    account = get_instagram_account()
    print(f"Found account: @{account['username']} ({account['instagram_user_id']})")

    # 2. Decrypt token
    access_token = decrypt_token(account["access_token"])
    print("Access token decrypted.")

    # 3. Fetch posts (or use the single specified post)
    if args.post_id:
        print(f"Targeting specific post: {args.post_id}")
        posts = [{"id": args.post_id, "media_type": "UNKNOWN"}]
    else:
        print("Fetching posts...")
        posts = fetch_posts(access_token, account["instagram_user_id"])
        print(f"Found {len(posts)} posts.")

    # 4. Fetch comments and build payloads
    all_payloads = []
    for post in posts:
        post_id = post["id"]
        media_type = post.get("media_type", "UNKNOWN")
        caption = (post.get("caption") or "")[:60] if "caption" in post else ""

        if caption:
            print(f"\n{'='*60}")
            print(f"Post: {post_id} - {caption}{'...' if len(post.get('caption', '')) > 60 else ''}")
        else:
            print(f"\n{'='*60}")
            print(f"Post: {post_id}")

        comments = fetch_comments(access_token, post_id)
        if not comments:
            print("  (no comments)")
            continue

        print(f"  Found {len(comments)} comments:")
        for comment in comments:
            from_data = comment.get("from", {})
            username = comment.get("username") or from_data.get("username", "unknown")
            text = comment.get("text", "")
            print(f"    @{username}: \"{text}\"")

            payload = build_webhook_payload(
                account_id=account["instagram_user_id"],
                comment=comment,
                media_id=post_id,
                media_type=media_type,
            )
            all_payloads.append(payload)

    if not all_payloads:
        print("\nNo comments found to process.")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"Processing {len(all_payloads)} comments through CommentProcessor...")
    print(f"{'='*60}")

    # 5. Run through CommentProcessor (async)
    summary = asyncio.run(process_comments(all_payloads))

    # 6. Print summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Comments processed:  {summary['processed']}")
    print(f"  DMs sent:            {summary['dms_sent']}")
    print(f"  DMs failed:          {summary['dms_failed']}")
    print(f"  DMs skipped (dedup): {summary['dms_deduped']}")
    print(f"  No automation:       {summary['no_automation']}")
    print(f"  Errors:              {summary['errors']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
