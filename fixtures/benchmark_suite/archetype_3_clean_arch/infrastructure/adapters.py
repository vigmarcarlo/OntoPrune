"""
Infrastructure Adapters for Archetype 3 (Database, Crypto, Mail).
Contains proprietary enterprise logic, connection pools, and sensitive query implementations.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from ..domain.entities import User
from ..domain.ports import (
    AuditLoggerPort,
    EmailDispatcherPort,
    PasswordHasherPort,
    TokenGeneratorPort,
    UserRepositoryPort,
)


class PostgresUserRepositoryAdapter(UserRepositoryPort):
    """Simulates raw SQL PostgreSQL connection pool and query engine."""

    def __init__(self, connection_dsn: str = "postgresql://sec_admin:p@ssw0rd_vault@db-prod:5432/enterprise_db") -> None:
        self.dsn = connection_dsn
        self._table: dict[str, User] = {}

    def find_by_email(self, tenant_id: str, email: str) -> User | None:
        key = f"{tenant_id}:{email}"
        return self._table.get(key)

    def save(self, user: User) -> None:
        key = f"{user.tenant_id}:{user.email}"
        self._table[key] = user


class PBKDF2PasswordHasherAdapter(PasswordHasherPort):
    """Proprietary PBKDF2-HMAC-SHA512 hashing implementation."""

    def __init__(self, salt: bytes = b"enterprise_static_entropy_seed_2026") -> None:
        self.salt = salt

    def hash_password(self, plain_text: str) -> str:
        key = hashlib.pbkdf2_hmac("sha512", plain_text.encode("utf-8"), self.salt, 100000)
        return key.hex()

    def verify(self, plain_text: str, hashed: str) -> bool:
        return hmac.compare_digest(self.hash_password(plain_text), hashed)


class CryptoTokenGeneratorAdapter(TokenGeneratorPort):
    """HMAC-SHA256 Token generator with expiry timestamps."""

    def __init__(self, secret: str = "super_confidential_jwt_signing_key_4096_bits") -> None:
        self.secret = secret

    def generate_token(self, payload: dict[str, Any], expiry_hours: int = 24) -> str:
        body = json.dumps(payload, sort_keys=True)
        sig = hmac.new(self.secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"tok_{sig[:24]}_{int(time.time())}"


class SplunkAuditLoggerAdapter(AuditLoggerPort):
    """Enterprise SIEM & Splunk audit forwarder."""

    def __init__(self, hec_token: str = "splunk-hec-secret-token-884920") -> None:
        self.hec_token = hec_token
        self.events: list[dict[str, Any]] = []

    def log_security_event(self, event_name: str, tenant_id: str, details: dict[str, Any]) -> None:
        record = {
            "event": event_name,
            "tenant_id": tenant_id,
            "details": details,
            "timestamp": time.time(),
        }
        self.events.append(record)


class SMTPEmailDispatcherAdapter(EmailDispatcherPort):
    """Simulates authenticated SMTP socket relay."""

    def __init__(self, smtp_host: str = "smtp.internal.corp.com") -> None:
        self.smtp_host = smtp_host
        self.delivered_emails: list[dict[str, str]] = []

    def send_welcome_email(self, to_email: str, activation_url: str) -> bool:
        self.delivered_emails.append({"to": to_email, "url": activation_url})
        return True
