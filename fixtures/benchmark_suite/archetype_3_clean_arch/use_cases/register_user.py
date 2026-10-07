"""
Use case: User Registration (Target of Archetype 3 evaluation).
"""

from __future__ import annotations

import re
import uuid
from ..domain.entities import Role, User, UserStatus
from ..domain.ports import (
    AuditLoggerPort,
    EmailDispatcherPort,
    PasswordHasherPort,
    TokenGeneratorPort,
    UserRepositoryPort,
)


class UserRegistrationError(Exception):
    pass


class EmailAlreadyExistsError(UserRegistrationError):
    pass


class InvalidPasswordComplexityError(UserRegistrationError):
    pass


class RegisterUserUseCase:
    """Orchestrates secure user registration according to enterprise business rules."""

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        hasher: PasswordHasherPort,
        token_gen: TokenGeneratorPort,
        audit_logger: AuditLoggerPort,
        email_dispatcher: EmailDispatcherPort,
    ) -> None:
        self.user_repo = user_repo
        self.hasher = hasher
        self.token_gen = token_gen
        self.audit_logger = audit_logger
        self.email_dispatcher = email_dispatcher

    def validate_password_strength(self, password: str) -> bool:
        """Enforces minimum 8 chars, 1 digit, and 1 uppercase."""
        if len(password) < 8:
            return False
        if not re.search(r"\d", password):
            return False
        if not re.search(r"[A-Z]", password):
            return False
        return True

    def execute(self, tenant_id: str, email: str, plain_password: str) -> User:
        """
        Executes registration protocol:
        1. Check tenant and password complexity. Raise InvalidPasswordComplexityError if weak.
        2. Verify email uniqueness within tenant. Raise EmailAlreadyExistsError if duplicate.
        3. Hash password via PasswordHasherPort.
        4. Generate activation token via TokenGeneratorPort.
        5. Persist user entity via UserRepositoryPort.
        6. Record security audit trail via AuditLoggerPort.
        7. Send welcome email via EmailDispatcherPort.
        """
        clean_email = email.strip().lower()

        if not self.validate_password_strength(plain_password):
            self.audit_logger.log_security_event(
                "REGISTRATION_FAILED_WEAK_PASSWORD",
                tenant_id,
                {"email": clean_email},
            )
            raise InvalidPasswordComplexityError("Password does not meet enterprise complexity.")

        existing = self.user_repo.find_by_email(tenant_id, clean_email)
        if existing is not None:
            self.audit_logger.log_security_event(
                "REGISTRATION_FAILED_DUPLICATE_EMAIL",
                tenant_id,
                {"email": clean_email},
            )
            raise EmailAlreadyExistsError(f"Email '{clean_email}' already registered.")

        hashed_pw = self.hasher.hash_password(plain_password)
        token = self.token_gen.generate_token({"email": clean_email, "tenant": tenant_id})

        user = User(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            email=clean_email,
            password_hash=hashed_pw,
            tenant_id=tenant_id,
            roles=[Role.USER],
            status=UserStatus.PENDING_ACTIVATION,
            activation_token=token,
        )

        self.user_repo.save(user)

        self.audit_logger.log_security_event(
            "USER_REGISTERED_SUCCESS",
            tenant_id,
            {"user_id": user.id, "email": clean_email},
        )

        activation_link = f"https://auth.enterprise.com/activate?token={token}"
        self.email_dispatcher.send_welcome_email(clean_email, activation_link)

        return user
