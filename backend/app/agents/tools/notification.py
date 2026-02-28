"""Notification / Webhook Tool.

Provides tools for sending notifications via webhooks, Slack, or email
when tasks complete or need attention.
"""

import json
from datetime import datetime, timezone

import aiohttp
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Timeout for sending notifications
NOTIFICATION_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class SendNotificationInput(BaseModel):
    """Input schema for send_notification tool."""

    message: str = Field(
        ...,
        description="Notification message content",
    )
    channel: str = Field(
        default="webhook",
        description="Notification channel: 'webhook' for generic webhooks, 'slack' for Slack, 'email' for email",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for 'webhook' or 'slack' channels. Required for webhook delivery.",
    )
    title: str | None = Field(
        default=None,
        description="Optional notification title or subject",
    )


# ---------------------------------------------------------------------------
# Channel handlers
# ---------------------------------------------------------------------------


async def _send_webhook(
    url: str, title: str | None, message: str
) -> dict:
    """Send a generic webhook notification via HTTP POST."""
    payload = {
        "title": title or "HyperAgent Notification",
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    timeout = aiohttp.ClientTimeout(total=NOTIFICATION_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            return {
                "status_code": response.status,
                "delivered": 200 <= response.status < 300,
            }


async def _send_slack(
    url: str, title: str | None, message: str
) -> dict:
    """Send a Slack notification via incoming webhook."""
    blocks = []
    if title:
        blocks.append({
            "type": "header",
            "text": {"type": "plain_text", "text": title, "emoji": True},
        })
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": message},
    })
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Sent by HyperAgent at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            }
        ],
    })

    payload = {
        "text": f"{title}: {message}" if title else message,
        "blocks": blocks,
    }

    timeout = aiohttp.ClientTimeout(total=NOTIFICATION_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as response:
            return {
                "status_code": response.status,
                "delivered": response.status == 200,
            }


def _send_email_placeholder(title: str | None, message: str) -> dict:
    """Placeholder for email notifications. Logs the intent."""
    logger.info(
        "email_notification_placeholder",
        title=title,
        message_length=len(message),
    )
    return {
        "delivered": False,
        "message": "Email notifications are not yet configured. Configure SMTP settings to enable email delivery.",
    }


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool(args_schema=SendNotificationInput)
async def send_notification(
    message: str,
    channel: str = "webhook",
    webhook_url: str | None = None,
    title: str | None = None,
) -> str:
    """Send a notification when a task completes or needs attention.

    Supports generic webhooks, Slack incoming webhooks, and email (placeholder).
    Use this to alert users about completed tasks, errors, or important events.

    Args:
        message: Notification message content
        channel: Notification channel ('webhook', 'slack', 'email')
        webhook_url: Webhook URL (required for 'webhook' and 'slack' channels)
        title: Optional notification title

    Returns:
        Notification delivery status
    """
    logger.info(
        "send_notification_invoked",
        channel=channel,
        title=title,
        message_length=len(message),
    )

    channel_lower = channel.lower()

    if channel_lower in ("webhook", "slack") and not webhook_url:
        return json.dumps({
            "success": False,
            "error": f"webhook_url is required for '{channel}' channel.",
        })

    try:
        if channel_lower == "webhook":
            result = await _send_webhook(webhook_url, title, message)
        elif channel_lower == "slack":
            result = await _send_slack(webhook_url, title, message)
        elif channel_lower == "email":
            result = _send_email_placeholder(title, message)
        else:
            return json.dumps({
                "success": False,
                "error": f"Unsupported channel: {channel}. Use 'webhook', 'slack', or 'email'.",
            })

        delivered = result.get("delivered", False)
        logger.info(
            "send_notification_completed",
            channel=channel_lower,
            delivered=delivered,
        )

        return json.dumps({
            "success": True,
            "channel": channel_lower,
            "delivered": delivered,
            **result,
        })

    except aiohttp.ClientError as e:
        logger.error("send_notification_client_error", channel=channel_lower, error=str(e))
        return json.dumps({
            "success": False,
            "channel": channel_lower,
            "error": f"Failed to send notification: {e}",
        })
    except Exception as e:
        logger.error("send_notification_failed", channel=channel_lower, error=str(e))
        return json.dumps({
            "success": False,
            "channel": channel_lower,
            "error": f"Notification failed: {e}",
        })
