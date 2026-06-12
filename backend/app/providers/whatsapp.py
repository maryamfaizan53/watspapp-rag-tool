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
    body: str               # text body ("" for unsupported types)
    message_id: str         # Meta message ID (for deduplication)
    display_name: str = ""  # sender's WhatsApp display name
    unsupported: bool = False  # True for voice/image/sticker/etc.


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
    Returns None for non-message events (status updates etc.).
    Returns a WhatsAppMessage with unsupported=True for non-text message
    types so the caller can reply politely instead of silently dropping.
    """
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]

        messages = value.get("messages")
        if not messages:
            return None

        msg = messages[0]
        contacts = value.get("contacts", [{}])
        display_name = contacts[0].get("profile", {}).get("name", "")

        if msg.get("type") != "text":
            return WhatsAppMessage(
                from_number=msg.get("from", ""),
                body="",
                message_id=msg.get("id", ""),
                display_name=display_name,
                unsupported=True,
            )

        return WhatsAppMessage(
            from_number=msg["from"],
            body=msg["text"]["body"],
            message_id=msg["id"],
            display_name=display_name,
        )
    except (KeyError, IndexError):
        return None


async def send_text_reply(
    access_token: str,
    phone_number_id: str,
    to_number: str,
    text: str,
) -> None:
    """Send a WhatsApp text message via Meta Cloud API."""
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    # NOTE: TLS verification MUST stay enabled — this call carries the
    # tenant's Meta access token. Never set verify=False here.
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("WhatsApp send error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
