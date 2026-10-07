"""
Unit tests for Archetype 3: RegisterUserUseCase.
"""

from unittest.mock import MagicMock
import pytest

from .domain.entities import Role, User, UserStatus
from .domain.ports import (
    AuditLoggerPort,
    EmailDispatcherPort,
    PasswordHasherPort,
    TokenGeneratorPort,
    UserRepositoryPort,
)
from .use_cases.register_user import (
    EmailAlreadyExistsError,
    InvalidPasswordComplexityError,
    RegisterUserUseCase,
)


@pytest.fixture
def mock_dependencies():
    repo = MagicMock(spec=UserRepositoryPort)
    hasher = MagicMock(spec=PasswordHasherPort)
    token_gen = MagicMock(spec=TokenGeneratorPort)
    audit = MagicMock(spec=AuditLoggerPort)
    email = MagicMock(spec=EmailDispatcherPort)

    repo.find_by_email.return_value = None
    hasher.hash_password.return_value = "hashed_pw_secret"
    token_gen.generate_token.return_value = "tok_valid_test_123"
    email.send_welcome_email.return_value = True

    use_case = RegisterUserUseCase(
        user_repo=repo,
        hasher=hasher,
        token_gen=token_gen,
        audit_logger=audit,
        email_dispatcher=email,
    )
    return use_case, repo, hasher, token_gen, audit, email


def test_successful_registration(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    user = use_case.execute("tenant_1", "Test@Example.com", "SecureP@ss123")

    assert user.email == "test@example.com"
    assert user.tenant_id == "tenant_1"
    assert user.password_hash == "hashed_pw_secret"
    assert user.status == UserStatus.PENDING_ACTIVATION
    assert user.activation_token == "tok_valid_test_123"
    assert Role.USER in user.roles

    repo.save.assert_called_once_with(user)
    audit.log_security_event.assert_called_once()
    assert audit.log_security_event.call_args[0][0] == "USER_REGISTERED_SUCCESS"
    email.send_welcome_email.assert_called_once()


def test_weak_password_raises_and_audits(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    with pytest.raises(InvalidPasswordComplexityError):
        use_case.execute("tenant_1", "usr@test.com", "weak")

    repo.save.assert_not_called()
    email.send_welcome_email.assert_not_called()
    audit.log_security_event.assert_called_once()
    assert audit.log_security_event.call_args[0][0] == "REGISTRATION_FAILED_WEAK_PASSWORD"


def test_password_missing_number_raises(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    with pytest.raises(InvalidPasswordComplexityError):
        use_case.execute("tenant_1", "usr@test.com", "PasswordWithoutNumber")


def test_password_missing_uppercase_raises(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    with pytest.raises(InvalidPasswordComplexityError):
        use_case.execute("tenant_1", "usr@test.com", "lowercase123")


def test_duplicate_email_raises_and_audits(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies
    repo.find_by_email.return_value = User(
        id="usr_old",
        email="dup@test.com",
        password_hash="***",
        tenant_id="tenant_1",
    )

    with pytest.raises(EmailAlreadyExistsError):
        use_case.execute("tenant_1", "dup@test.com", "SecureP@ss123")

    repo.save.assert_not_called()
    email.send_welcome_email.assert_not_called()
    audit.log_security_event.assert_called_once()
    assert audit.log_security_event.call_args[0][0] == "REGISTRATION_FAILED_DUPLICATE_EMAIL"


def test_email_is_trimmed_and_lowercased(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    user = use_case.execute("tenant_1", "   SPACES@domain.com  ", "SecureP@ss123")
    assert user.email == "spaces@domain.com"
    repo.find_by_email.assert_called_once_with("tenant_1", "spaces@domain.com")


def test_welcome_email_contains_activation_token(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    use_case.execute("tenant_1", "tok@test.com", "SecureP@ss123")
    sent_url = email.send_welcome_email.call_args[0][1]
    assert "token=tok_valid_test_123" in sent_url


def test_hasher_called_with_exact_plain_password(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    use_case.execute("tenant_1", "hash@test.com", "ExactPassword99")
    hasher.hash_password.assert_called_once_with("ExactPassword99")


def test_token_generator_receives_tenant_and_email(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    use_case.execute("tenant_abc", "payload@test.com", "SecureP@ss123")
    payload = token_gen.generate_token.call_args[0][0]
    assert payload["email"] == "payload@test.com"
    assert payload["tenant"] == "tenant_abc"


def test_user_id_generated_with_usr_prefix(mock_dependencies):
    use_case, repo, hasher, token_gen, audit, email = mock_dependencies

    user = use_case.execute("tenant_1", "id@test.com", "SecureP@ss123")
    assert user.id.startswith("usr_")
