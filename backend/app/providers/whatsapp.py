import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from twilio.request_validator import RequestValidator

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppMessage:
    from_number: str       # E.164 sender number
    body: str              # text body (may be empty for media-only messages)
    media_url: Optional[str] = None
    media_content_type: Optional[str] = None


class InvalidTwilioSignatureError(Exception):
    pass


def validate_signature(
    auth_token: str,
    request_url: str,
    post_params: dict,
    signature: str,
) -> None:
    """Raise InvalidTwilioSignatureError if the Twilio HMAC signature is invalid."""
    validator = RequestValidator(auth_token)
    if not validator.validate(request_url, post_params, signature):
        raise InvalidTwilioSignatureError("Invalid X-Twilio-Signature")


def parse_webhook(form_data: dict) -> WhatsAppMessage:
    """Parse a Twilio WhatsApp webhook form dict into a WhatsAppMessage."""
    return WhatsAppMessage(
        from_number=form_data.get("From", "").replace("whatsapp:", ""),
        body=form_data.get("Body", ""),
        media_url=form_data.get("MediaUrl0"),
        media_content_type=form_data.get("MediaContentType0"),
    )


async def download_media(media_url: str, account_sid: str, auth_token: str) -> bytes:
    """Download media file from Twilio CDN using Basic Auth."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(media_url, auth=(account_sid, auth_token))
        resp.raise_for_status()
        return resp.content


async def send_text_reply(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    text: str,
) -> None:
    """Send a WhatsApp text message via Twilio API."""
    from twilio.rest import Client

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{to_number}",
            body=text,
        )
    except Exception as exc:
        logger.error("Failed to send WhatsApp reply to %s: %s", to_number, exc)
