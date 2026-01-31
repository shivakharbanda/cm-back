#!/usr/bin/env python3
"""Send a DM to a specific Instagram user who commented on your posts.

Bypasses the automation/RabbitMQ pipeline and directly calls the Instagram API.

Usage (from cm-back directory):
    uv run python tools/send_dm.py
    uv run python tools/send_dm.py --message "Custom message here"
    uv run python tools/send_dm.py --target other_user
"""

import argparse
import os
import sys

import httpx
import psycopg
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_URL = os.getenv("INSTAGRAM_GRAPH_API_URL", "https://graph.instagram.com")
DEFAULT_TARGET = "garvit.05"
DEFAULT_MESSAGE = "Hey! Thanks for your comment!"


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


def send_dm(access_token: str, sender_id: str, comment_id: str, message: str) -> dict:
    """Send a DM to a commenter using their comment_id."""
    resp = httpx.post(
        f"{GRAPH_API_URL}/{sender_id}/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "recipient": {"comment_id": comment_id},
            "message": {"text": message},
        },
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Send a DM to an Instagram user who commented on your posts."
    )
    parser.add_argument(
        "--message", "-m", default=DEFAULT_MESSAGE, help="Message to send"
    )
    parser.add_argument(
        "--target", "-t", default=DEFAULT_TARGET, help="Target username to DM"
    )
    args = parser.parse_args()

    # 1. Get account from DB
    print("Connecting to database...")
    account = get_instagram_account()
    print(f"Found account: @{account['username']} ({account['instagram_user_id']})")

    # 2. Decrypt token
    access_token = decrypt_token(account["access_token"])
    print("Access token decrypted.")

    # 3. Fetch posts
    print("Fetching posts...")
    posts = fetch_posts(access_token, account["instagram_user_id"])
    print(f"Found {len(posts)} posts.")

    # 4. List all comments and search for the target user
    target_comment = None
    for post in posts:
        caption = (post.get("caption") or "")[:60]
        permalink = post.get("permalink", "")
        print(f"\n{'='*60}")
        print(f"Post: {post['id']}")
        print(f"Caption: {caption}{'...' if len(post.get('caption') or '') > 60 else ''}")
        print(f"Type: {post.get('media_type', 'unknown')}")
        print(f"Link: {permalink}")
        print(f"Posted: {post.get('timestamp', 'unknown')}")
        print(f"{'-'*60}")

        comments = fetch_comments(access_token, post["id"])
        if not comments:
            print("  (no comments)")
            continue

        print(f"  Comments ({len(comments)}):")
        for comment in comments:
            from_data = comment.get("from", {})
            username = comment.get("username") or from_data.get("username", "unknown")
            text = comment.get("text", "")
            timestamp = comment.get("timestamp", "unknown")
            marker = " <-- TARGET" if username.lower() == args.target.lower() else ""
            print(f"    @{username} ({timestamp}):{marker}")
            print(f"      \"{text}\"")

            if username.lower() == args.target.lower() and target_comment is None:
                target_comment = comment

    print(f"\n{'='*60}")
    if not target_comment:
        print(f"No comment from @{args.target} found on any post.")
        sys.exit(1)

    # 5. Send DM
    print(f"\nSending DM to @{args.target}: \"{args.message}\"")
    result = send_dm(
        access_token, account["instagram_user_id"], target_comment["id"], args.message
    )
    print(f"DM sent! Message ID: {result.get('message_id', 'unknown')}")


if __name__ == "__main__":
    main()
