import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


@dataclass
class WhatsAppMessage:
    from_number: str        # E.164 sender number e.g. "923001234567"
    body: str               # text body
    message_id: str         # Meta message ID (for deduplication)
    display_name: str = ""  # sender's WhatsApp display name


class InvalidSignatureError(Exception):
    pass


def verify_signature(app_secret: str, payload_bytes: bytes, signature_header: str) -> None:
    """Raise InvalidSignatureError if the Meta X-Hub-Signature-256 is invalid."""
    expected = "sha256=" + hmac.new(
        app_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise InvalidSignatureError("Invalid X-Hub-Signature-256")


def parse_webhook(payload: dict) -> Optional[WhatsAppMessage]:
    """
    Parse a Meta WhatsApp Cloud API webhook payload.
    Returns None if the event is not an incoming text message.
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        messages = value.get("messages")
        if not messages:
            return None

        msg = messages[0]
        if msg.get("type") != "text":
            return None

        contacts = value.get("contacts", [{}])
        display_name = contacts[0].get("profile", {}).get("name", "")

        return WhatsAppMessage(
            from_number=msg["from"],
            body=msg["text"]["body"],
            message_id=msg["id"],
            display_name=display_name,
        )
    except (KeyError, IndexError):
        return None


def _send_whatsapp_sync(access_token: str, phone_number_id: str, to_number: str, text: str) -> None:
    """Synchronous WhatsApp send — runs in thread executor to avoid httpx timeout issues."""
    import urllib.request
    import json as _json
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    data = _json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        if resp.status != 200:
            body = resp.read().decode()
            logger.error("Failed to send WhatsApp reply to %s: %s %s", to_number, resp.status, body)


async def send_text_reply(
    access_token: str,
    phone_number_id: str,
    to_number: str,
    text: str,
) -> None:
    """Send a WhatsApp text message via Meta Cloud API."""
    import asyncio
    import functools
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            functools.partial(_send_whatsapp_sync, access_token, phone_number_id, to_number, text),
        )
        return
    except Exception as exc:
        logger.warning("sync WhatsApp send failed, trying httpx: %s", exc)

    # Fallback: httpx with longer timeout
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("Failed to send WhatsApp reply to %s: %s %s", to_number, resp.status_code, resp.text)
        resp.raise_for_status()
