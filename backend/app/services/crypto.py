"""
Fernet encryption for tenant channel secrets (bot tokens, access tokens, app secrets).

Backwards compatible: decrypt_secret() returns the value unchanged when it is
legacy plaintext (or when no ENCRYPTION_KEY is configured), so existing rows
keep working. New writes are always encrypted when a key is present.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Optional[Fernet] = None

if settings.encryption_key:
    try:
        _fernet = Fernet(settings.encryption_key.encode())
    except Exception as exc:  # malformed key
        logger.error("ENCRYPTION_KEY is invalid — secrets will NOT be encrypted: %s", exc)
        _fernet = None
else:
    logger.warning(
        "ENCRYPTION_KEY is not set — channel secrets will be stored in PLAINTEXT. "
        "Set it before going to production."
    )

_PREFIX = "enc:v1:"  # marks encrypted values so legacy plaintext is detectable


def encryption_enabled() -> bool:
    return _fernet is not None


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    """Encrypt a secret for storage. No-op if empty or no key configured."""
    if not value or _fernet is None:
        return value
    if value.startswith(_PREFIX):  # already encrypted — don't double-encrypt
        return value
    return _PREFIX + _fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    """Decrypt a stored secret. Legacy plaintext values pass through unchanged."""
    if not value:
        return value
    if not value.startswith(_PREFIX):
        return value  # legacy plaintext row
    if _fernet is None:
        logger.error("Encrypted secret found but ENCRYPTION_KEY is not set — cannot decrypt.")
        return None
    try:
        return _fernet.decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt channel secret — wrong ENCRYPTION_KEY?")
        return None
