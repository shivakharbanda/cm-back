#!/usr/bin/env python3
"""Send a carousel (generic template) DM to any user whose comment contains a keyword.

Bypasses the automation/RabbitMQ pipeline and directly calls the Instagram API.
Uses the Generic Template format for rich carousel messages.

IMPORTANT: Each comment_id can only be used once for messaging. Once a DM has been
sent using a comment_id, it's consumed and can't be reused. This script tries
matching comments from newest to oldest until one succeeds.

Reference: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/generic-template

Usage (from cm-back directory):
    uv run python tools/send_carousel.py
    uv run python tools/send_carousel.py --keyword "SOME_KEYWORD"
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
DEFAULT_KEYWORD = "Comment"

DUMMY_CAROUSEL = [
    {
        "title": "Minimalist Watch",
        "subtitle": "$149.99 - Elegant everyday timepiece",
        "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500",
        "buttons": [
            {
                "type": "web_url",
                "url": "https://example.com/products/watch",
                "title": "Shop Now",
            },
            {
                "type": "web_url",
                "url": "https://example.com/products/watch/reviews",
                "title": "Read Reviews",
            },
            {
                "type": "web_url",
                "url": "https://example.com/size-guide",
                "title": "Size Guide",
            },
        ],
    },
    {
        "title": "Wireless Headphones",
        "subtitle": "$79.99 - 30hr battery, noise cancelling",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500",
        "buttons": [
            {
                "type": "web_url",
                "url": "https://example.com/products/headphones",
                "title": "Shop Now",
            },
            {
                "type": "web_url",
                "url": "https://example.com/products/headphones/compare",
                "title": "Compare Models",
            },
        ],
    },
    {
        "title": "Running Shoes Pro",
        "subtitle": "$119.99 - Lightweight & breathable",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500",
        "buttons": [
            {
                "type": "web_url",
                "url": "https://example.com/products/shoes",
                "title": "Shop Now",
            },
            {
                "type": "web_url",
                "url": "https://example.com/products/shoes/colors",
                "title": "View Colors",
            },
            {
                "type": "web_url",
                "url": "https://example.com/shoe-size-guide",
                "title": "Size Guide",
            },
        ],
    },
    {
        "title": "Polaroid Camera",
        "subtitle": "$89.99 - Instant prints, retro vibes",
        "image_url": "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500",
        "buttons": [
            {
                "type": "web_url",
                "url": "https://example.com/products/camera",
                "title": "Shop Now",
            },
            {
                "type": "web_url",
                "url": "https://example.com/products/camera/gallery",
                "title": "Sample Photos",
            },
        ],
    },
    {
        "title": "Classic Sunglasses",
        "subtitle": "$59.99 - UV400 protection, unisex",
        "image_url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500",
        "buttons": [
            {
                "type": "web_url",
                "url": "https://example.com/products/sunglasses",
                "title": "Shop Now",
            },
            {
                "type": "web_url",
                "url": "https://example.com/products/sunglasses/styles",
                "title": "Browse Styles",
            },
            {
                "type": "web_url",
                "url": "https://example.com/try-on",
                "title": "Virtual Try-On",
            },
        ],
    },
]


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


def send_carousel(
    access_token: str, sender_id: str, comment_id: str, elements: list[dict]
) -> dict | None:
    """Send a carousel (generic template) DM to a commenter.

    Returns the API response on success, or None if the comment_id was already used.
    """
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements,
                },
            }
        },
    }

    resp = httpx.post(
        f"{GRAPH_API_URL}/{sender_id}/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if resp.status_code == 200:
        return resp.json()

    print(f"    Failed ({resp.status_code}): comment_id may already be used, trying next...")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Send a carousel DM to users whose comments contain a keyword."
    )
    parser.add_argument(
        "--keyword", "-k", default=DEFAULT_KEYWORD, help="Keyword to match in comments (case-insensitive)"
    )
    args = parser.parse_args()

    keyword = args.keyword.lower()

    # 1. Get account from DB
    print("Connecting to database...")
    account = get_instagram_account()
    print(f"Found account: @{account['username']} ({account['instagram_user_id']})")

    # 2. Decrypt token
    access_token = decrypt_token(account["access_token"])
    print("Access token decrypted.")

    # 3. Fetch posts and collect comments matching the keyword
    print(f"Fetching posts and searching for keyword \"{args.keyword}\"...")
    posts = fetch_posts(access_token, account["instagram_user_id"])
    print(f"Found {len(posts)} posts.")

    matching_comments = []
    for post in posts:
        caption = (post.get("caption") or "")[:60]
        print(f"\n  Checking post {post['id']} - {caption}...")
        comments = fetch_comments(access_token, post["id"])
        for comment in comments:
            from_data = comment.get("from", {})
            username = comment.get("username") or from_data.get("username", "unknown")
            text = comment.get("text", "")

            if keyword in text.lower():
                matching_comments.append(comment)
                print(f"    MATCH: @{username} ({comment['timestamp']}): \"{text}\"")
            else:
                print(f"    skip:  @{username} ({comment['timestamp']}): \"{text}\"")

    if not matching_comments:
        print(f"\nNo comments containing \"{args.keyword}\" found on any post.")
        sys.exit(1)

    print(f"\nFound {len(matching_comments)} comments matching \"{args.keyword}\".")

    # 4. Try sending carousel using each matching comment_id
    print("\nCarousel cards:")
    for i, card in enumerate(DUMMY_CAROUSEL, 1):
        print(f"  Card {i}: {card['title']} - {card['subtitle']}")

    sent_count = 0
    for comment in matching_comments:
        from_data = comment.get("from", {})
        username = comment.get("username") or from_data.get("username", "unknown")
        print(f"\n  Trying @{username} comment_id {comment['id']} (\"{comment['text']}\")...")
        result = send_carousel(
            access_token,
            account["instagram_user_id"],
            comment["id"],
            DUMMY_CAROUSEL,
        )
        if result:
            print(f"    Carousel sent to @{username}! Message ID: {result.get('message_id', 'unknown')}")
            sent_count += 1

    print(f"\nDone. Sent {sent_count} carousel(s) out of {len(matching_comments)} matching comments.")
    if sent_count == 0:
        print("All matching comment_ids were already used. Users need to comment again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
