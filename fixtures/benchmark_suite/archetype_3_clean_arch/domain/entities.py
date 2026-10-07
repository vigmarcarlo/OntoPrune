"""
Archetype 3 Domain Entities and Value Objects.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class UserStatus(str, Enum):
    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    AUDITOR = "auditor"


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    tenant_id: str
    roles: list[Role] = field(default_factory=lambda: [Role.USER])
    status: UserStatus = UserStatus.PENDING_ACTIVATION
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    activation_token: str | None = None
