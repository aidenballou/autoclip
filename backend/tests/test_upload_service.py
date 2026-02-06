"""Tests for upload service OAuth handling."""
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException

from app.api import routes
from app.api.schemas import OAuthCallbackRequest
from app.models.account import Account, AuthStatus, Platform
from app.models.youtube_oauth_pending import YouTubeOAuthPending
from app.services.upload_service import OAuthUpstreamError, YouTubeUploadService


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalarResult(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, account: Account):
        self._account = account
        self._pending = []

    async def get(self, model, object_id):
        if model is Account and object_id == self._account.id:
            return self._account
        return None

    async def execute(self, query):
        entities = [desc.get("entity") for desc in query.column_descriptions if desc.get("entity")]
        if YouTubeOAuthPending in entities:
            return _FakeExecuteResult(self._pending)
        return _FakeExecuteResult([])

    def add(self, instance):
        if isinstance(instance, YouTubeOAuthPending):
            self._pending.append(instance)

    async def delete(self, instance):
        if instance in self._pending:
            self._pending.remove(instance)

    async def flush(self):
        return None

    async def refresh(self, _):
        return None


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class _FakeClient:
    def __init__(self, post_response=None, get_response=None, error=None, **kwargs):
        self._post_response = post_response
        self._get_response = get_response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self._error:
            raise self._error
        return self._post_response

    async def get(self, *args, **kwargs):
        if self._error:
            raise self._error
        return self._get_response


class _FakeNicheService:
    def __init__(self, db):
        self.db = db

    async def update_account_auth(
        self,
        account_id: int,
        auth_status: AuthStatus,
        access_token=None,
        refresh_token=None,
        token_expires_at=None,
        platform_user_id=None,
    ):
        account = await self.db.get(Account, account_id)
        account.auth_status = auth_status
        if access_token is not None:
            account.access_token = access_token
        if refresh_token is not None:
            account.refresh_token = refresh_token
        if token_expires_at is not None:
            account.token_expires_at = token_expires_at
        if platform_user_id is not None:
            account.platform_user_id = platform_user_id
        return account


@pytest.fixture
def youtube_account():
    return Account(
        id=1,
        niche_id=1,
        platform=Platform.YOUTUBE_SHORTS,
        handle="@channel",
        auth_status=AuthStatus.NOT_CONNECTED,
    )


@pytest.fixture(autouse=True)
def oauth_settings(monkeypatch):
    from app.services import upload_service

    monkeypatch.setattr(upload_service.settings, "youtube_client_id", "test-client-id")
    monkeypatch.setattr(upload_service.settings, "youtube_client_secret", "test-client-secret")


@pytest.mark.asyncio
async def test_complete_oauth_success(monkeypatch, youtube_account):
    from app.services import upload_service

    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)
    token_response = _FakeResponse(
        status_code=200,
        payload={
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 3600,
        },
    )
    channels_response = _FakeResponse(
        status_code=200,
        payload={
            "items": [
                {
                    "id": "channel_1",
                    "snippet": {"title": "My Channel", "customUrl": "mychannel"},
                }
            ]
        },
    )

    monkeypatch.setattr(upload_service, "NicheService", _FakeNicheService)
    monkeypatch.setattr(
        upload_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(post_response=token_response, get_response=channels_response),
    )

    result = await service.complete_oauth(
        account_id=1,
        authorization_code="code",
        redirect_uri="http://localhost:5173/oauth/callback",
    )

    assert result.status == "connected"
    account = result.account
    assert account is not None
    assert account.auth_status == AuthStatus.CONNECTED
    assert account.access_token == "access123"
    assert account.refresh_token == "refresh123"
    assert account.platform_user_id == "channel_1"
    assert account.display_name == "My Channel"
    assert account.handle == "@mychannel"
    assert account.token_expires_at is not None
    assert account.token_expires_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_complete_oauth_provider_rejection(monkeypatch, youtube_account):
    from app.services import upload_service

    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)
    token_response = _FakeResponse(
        status_code=400,
        payload={"error": "invalid_grant", "error_description": "Bad Request"},
    )

    monkeypatch.setattr(
        upload_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(post_response=token_response),
    )

    with pytest.raises(ValueError, match="invalid_grant"):
        await service.complete_oauth(
            account_id=1,
            authorization_code="bad-code",
            redirect_uri="http://localhost:5173/oauth/callback",
        )


@pytest.mark.asyncio
async def test_complete_oauth_timeout_maps_upstream_error(monkeypatch, youtube_account):
    from app.services import upload_service

    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)

    monkeypatch.setattr(
        upload_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(post_response=None, get_response=None, error=httpx.TimeoutException("timeout")),
    )

    with pytest.raises(OAuthUpstreamError, match="timed out"):
        await service.complete_oauth(
            account_id=1,
            authorization_code="code",
            redirect_uri="http://localhost:5173/oauth/callback",
        )


@pytest.mark.asyncio
async def test_refresh_token_if_needed_skips_when_token_still_valid(youtube_account):
    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)
    youtube_account.refresh_token = "refresh123"
    youtube_account.token_expires_at = datetime.utcnow() + timedelta(minutes=10)

    updated = await service.refresh_token_if_needed(youtube_account)
    assert updated is youtube_account


@pytest.mark.asyncio
async def test_refresh_token_failure_marks_account_expired(monkeypatch, youtube_account):
    from app.services import upload_service

    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)
    youtube_account.refresh_token = "refresh123"
    youtube_account.token_expires_at = datetime.utcnow() - timedelta(minutes=1)

    token_response = _FakeResponse(
        status_code=400,
        payload={"error": "invalid_grant", "error_description": "Token expired"},
    )

    monkeypatch.setattr(upload_service, "NicheService", _FakeNicheService)
    monkeypatch.setattr(
        upload_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(post_response=token_response),
    )

    with pytest.raises(ValueError, match="re-authorization required"):
        await service.refresh_token_if_needed(youtube_account)

    assert youtube_account.auth_status == AuthStatus.EXPIRED


@pytest.mark.asyncio
async def test_complete_oauth_selection_required_for_multiple_channels(monkeypatch, youtube_account):
    from app.services import upload_service

    fake_db = _FakeDB(youtube_account)
    service = YouTubeUploadService(fake_db)
    token_response = _FakeResponse(
        status_code=200,
        payload={
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 3600,
        },
    )
    channels_response = _FakeResponse(
        status_code=200,
        payload={
            "items": [
                {"id": "channel_1", "snippet": {"title": "Channel One", "customUrl": "chanone"}},
                {"id": "channel_2", "snippet": {"title": "Channel Two", "customUrl": "chantwo"}},
            ]
        },
    )

    monkeypatch.setattr(
        upload_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeClient(post_response=token_response, get_response=channels_response),
    )

    result = await service.complete_oauth(
        account_id=1,
        authorization_code="code",
        redirect_uri="http://localhost:5173/oauth/callback",
    )

    assert result.status == "selection_required"
    assert result.selection_token is not None
    assert result.channels is not None
    assert len(result.channels) == 2


@pytest.mark.asyncio
async def test_oauth_callback_route_returns_502_for_upstream_errors(monkeypatch):
    async def _raise_upstream(self, account_id, authorization_code, redirect_uri):
        raise OAuthUpstreamError("Google OAuth timed out. Please try again.")

    monkeypatch.setattr(routes.UploadService, "complete_oauth", _raise_upstream)

    with pytest.raises(HTTPException) as exc:
        await routes.oauth_callback(
            account_id=1,
            data=OAuthCallbackRequest(
                code="abc",
                redirect_uri="http://localhost:5173/oauth/callback",
            ),
            db=object(),
        )

    assert exc.value.status_code == 502
