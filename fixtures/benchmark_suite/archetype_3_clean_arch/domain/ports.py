"""
Archetype 3 Hexagonal Ports (Interfaces).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from .entities import User


class UserRepositoryPort(ABC):
    """Port for persistence operations."""

    @abstractmethod
    def find_by_email(self, tenant_id: str, email: str) -> User | None:
        pass

    @abstractmethod
    def save(self, user: User) -> None:
        pass


class PasswordHasherPort(ABC):
    """Port for password hashing and verification."""

    @abstractmethod
    def hash_password(self, plain_text: str) -> str:
        pass

    @abstractmethod
    def verify(self, plain_text: str, hashed: str) -> bool:
        pass


class TokenGeneratorPort(ABC):
    """Port for cryptographically secure token generation."""

    @abstractmethod
    def generate_token(self, payload: dict[str, Any], expiry_hours: int = 24) -> str:
        pass


class AuditLoggerPort(ABC):
    """Port for security and compliance audit event trail."""

    @abstractmethod
    def log_security_event(self, event_name: str, tenant_id: str, details: dict[str, Any]) -> None:
        pass


class EmailDispatcherPort(ABC):
    """Port for transactional email delivery."""

    @abstractmethod
    def send_welcome_email(self, to_email: str, activation_url: str) -> bool:
        pass
