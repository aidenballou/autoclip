"""Upload service for direct platform uploads."""
import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.account import Account, Platform, AuthStatus
from app.models.clip import Clip
from app.models.job import Job, JobType, JobStatus
from app.models.niche import Niche
from app.models.project import Project
from app.models.youtube_oauth_pending import YouTubeOAuthPending
from app.services.niche_service import NicheService
from app.utils.ffmpeg import ExportPreset, export_clip_enhanced

logger = logging.getLogger(__name__)
OAUTH_HTTP_TIMEOUT_SECONDS = 15.0
UPLOAD_HTTP_TIMEOUT_SECONDS = 120.0


class OAuthUpstreamError(RuntimeError):
    """Raised when OAuth upstream provider is unreachable."""


@dataclass
class YouTubeChannel:
    """YouTube channel discovered from OAuth access token."""
    channel_id: str
    title: str
    handle: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "channel_id": self.channel_id,
            "title": self.title,
            "handle": self.handle,
        }


@dataclass
class OAuthCompletionResult:
    """Result of OAuth completion."""
    status: str
    account: Optional[Account] = None
    account_id: Optional[int] = None
    selection_token: Optional[str] = None
    channels: Optional[List[YouTubeChannel]] = None


def _extract_oauth_error_detail(response: httpx.Response) -> str:
    """Extract concise OAuth error detail from provider response."""
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        code = payload.get("error")
        description = payload.get("error_description")

        parts: List[str] = []
        if code:
            parts.append(str(code))
        if description:
            parts.append(str(description))
        if parts:
            return ": ".join(parts)

    return f"HTTP {response.status_code}"


@dataclass
class UploadResult:
    """Result of an upload attempt."""
    success: bool
    platform: str
    account_id: int
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


class YouTubeUploadService:
    """
    Service for uploading videos to YouTube Shorts.
    
    Requires YouTube Data API v3 credentials.
    OAuth2 flow must be completed to get access tokens.
    """
    
    YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
    YOUTUBE_CHANNELS_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
    YOUTUBE_API_SERVICE = "youtube"
    YOUTUBE_API_VERSION = "v3"
    
    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize_handle(self, channel_id: str, custom_url: Optional[str]) -> str:
        """Normalize a channel handle string."""
        if custom_url:
            if custom_url.startswith("@"):
                return custom_url
            return f"@{custom_url}"
        return f"channel:{channel_id}"

    async def _fetch_channels(self, access_token: str) -> List[YouTubeChannel]:
        """Fetch channels available to the authenticated YouTube user."""
        try:
            async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "snippet", "mine": "true", "maxResults": 50},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.TimeoutException as exc:
            raise OAuthUpstreamError("YouTube channel lookup timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            raise OAuthUpstreamError("Unable to reach YouTube API for channel lookup.") from exc

        if response.status_code != 200:
            detail = _extract_oauth_error_detail(response)
            raise ValueError(f"Unable to load YouTube channels: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("Unable to load YouTube channels: invalid provider response") from exc

        channels: List[YouTubeChannel] = []
        for item in payload.get("items", []):
            channel_id = item.get("id")
            snippet = item.get("snippet") or {}
            title = snippet.get("title") or "Untitled channel"
            custom_url = snippet.get("customUrl")
            if not channel_id:
                continue
            channels.append(
                YouTubeChannel(
                    channel_id=channel_id,
                    title=title,
                    handle=self._normalize_handle(channel_id, custom_url),
                )
            )

        return channels

    async def _persist_connected_account(
        self,
        account_id: int,
        token_data: Dict[str, Any],
        channel: YouTubeChannel,
    ) -> Account:
        """Persist auth tokens and selected YouTube channel on account."""
        niche_service = NicheService(self.db)
        account = await niche_service.update_account_auth(
            account_id=account_id,
            auth_status=AuthStatus.CONNECTED,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            platform_user_id=channel.channel_id,
        )
        account.display_name = channel.title
        account.handle = channel.handle
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def _clear_expired_pending(self) -> None:
        """Delete expired pending OAuth selections."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(YouTubeOAuthPending).where(YouTubeOAuthPending.expires_at < now)
        )
        for pending in result.scalars().all():
            await self.db.delete(pending)
        await self.db.flush()
    
    async def get_oauth_url(self, account_id: int, redirect_uri: str) -> str:
        """
        Generate OAuth URL for YouTube authorization.
        
        Returns URL to redirect user to for authorization.
        """
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        if account.platform != Platform.YOUTUBE_SHORTS:
            raise ValueError("Account is not a YouTube account")
        
        # In production, use Google OAuth client library
        # For now, return a placeholder that indicates the flow
        client_id = settings.youtube_client_id
        
        if not client_id:
            raise ValueError(
                "YouTube API credentials not configured. "
                "Set youtube_client_id and youtube_client_secret in your .env file."
            )
        
        scopes = f"{self.YOUTUBE_UPLOAD_SCOPE} {self.YOUTUBE_CHANNELS_READ_SCOPE}"
        oauth_params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "access_type": "offline",
            "include_granted_scopes": "true",
            # Force consent so reconnect upgrades granted scopes reliably.
            "prompt": "consent",
            "state": str(account_id),
        }
        oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(oauth_params)}"
        
        return oauth_url
    
    async def complete_oauth(
        self,
        account_id: int,
        authorization_code: str,
        redirect_uri: str,
    ) -> OAuthCompletionResult:
        """
        Complete OAuth flow by exchanging authorization code for tokens.
        
        Returns updated account with tokens.
        """
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        client_id = settings.youtube_client_id
        client_secret = settings.youtube_client_secret
        
        if not client_id or not client_secret:
            raise ValueError("YouTube API credentials not configured")
        
        try:
            async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": authorization_code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
        except httpx.TimeoutException as exc:
            logger.warning(
                "YouTube OAuth token exchange timed out for account_id=%s",
                account_id,
            )
            raise OAuthUpstreamError("Google OAuth timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "YouTube OAuth token exchange network error for account_id=%s: %s",
                account_id,
                type(exc).__name__,
            )
            raise OAuthUpstreamError(
                "Unable to reach Google OAuth service. Please try again."
            ) from exc

        if response.status_code != 200:
            detail = _extract_oauth_error_detail(response)
            logger.info(
                "YouTube OAuth token exchange rejected for account_id=%s status=%s detail=%s",
                account_id,
                response.status_code,
                detail,
            )
            raise ValueError(f"OAuth token exchange failed: {detail}")

        try:
            token_data = response.json()
        except ValueError as exc:
            logger.warning(
                "YouTube OAuth token exchange returned invalid JSON for account_id=%s",
                account_id,
            )
            raise ValueError("OAuth token exchange failed: invalid provider response") from exc
        
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("OAuth token exchange failed: access token missing")

        channels = await self._fetch_channels(access_token)
        if not channels:
            raise ValueError("No YouTube channels found for this Google account")

        if len(channels) == 1:
            account = await self._persist_connected_account(account_id, token_data, channels[0])
            return OAuthCompletionResult(status="connected", account=account)

        await self._clear_expired_pending()
        selection_token = secrets.token_urlsafe(32)
        pending = YouTubeOAuthPending(
            account_id=account_id,
            selection_token=selection_token,
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
            channels_json=json.dumps([c.to_dict() for c in channels]),
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        self.db.add(pending)
        await self.db.flush()

        return OAuthCompletionResult(
            status="selection_required",
            account_id=account_id,
            selection_token=selection_token,
            channels=channels,
        )
    
    async def refresh_token_if_needed(self, account: Account) -> Account:
        """Refresh access token if expired or about to expire."""
        if not account.refresh_token:
            raise ValueError("No refresh token available")
        
        # Check if token is expired or will expire in next 5 minutes
        if account.token_expires_at and account.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
            return account  # Token still valid
        
        client_id = settings.youtube_client_id
        client_secret = settings.youtube_client_secret
        
        if not client_id or not client_secret:
            raise ValueError("YouTube API credentials not configured")

        try:
            async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": account.refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.TimeoutException as exc:
            logger.warning(
                "YouTube token refresh timed out for account_id=%s",
                account.id,
            )
            raise OAuthUpstreamError("Google token refresh timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "YouTube token refresh network error for account_id=%s: %s",
                account.id,
                type(exc).__name__,
            )
            raise OAuthUpstreamError(
                "Unable to reach Google OAuth service for token refresh."
            ) from exc

        if response.status_code != 200:
            detail = _extract_oauth_error_detail(response)
            logger.info(
                "YouTube token refresh rejected for account_id=%s status=%s detail=%s",
                account.id,
                response.status_code,
                detail,
            )
            # Mark account as expired
            niche_service = NicheService(self.db)
            await niche_service.update_account_auth(
                account_id=account.id,
                auth_status=AuthStatus.EXPIRED,
            )
            raise ValueError("Failed to refresh token - re-authorization required")

        try:
            token_data = response.json()
        except ValueError as exc:
            logger.warning(
                "YouTube token refresh returned invalid JSON for account_id=%s",
                account.id,
            )
            raise ValueError("Token refresh failed: invalid provider response") from exc
        
        # Update account with new access token
        niche_service = NicheService(self.db)
        account = await niche_service.update_account_auth(
            account_id=account.id,
            auth_status=AuthStatus.CONNECTED,
            access_token=token_data.get("access_token"),
            token_expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600)),
        )
        
        return account

    async def get_pending_channels(
        self,
        account_id: int,
        selection_token: str,
    ) -> Dict[str, Any]:
        """Fetch pending channel options for an account."""
        await self._clear_expired_pending()
        result = await self.db.execute(
            select(YouTubeOAuthPending).where(
                YouTubeOAuthPending.account_id == account_id,
                YouTubeOAuthPending.selection_token == selection_token,
            )
        )
        pending = result.scalar_one_or_none()
        if not pending:
            raise ValueError("No pending channel selection found. Please reconnect the account.")

        try:
            channels = json.loads(pending.channels_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Pending channel selection is corrupted. Please reconnect.") from exc

        return {
            "account_id": account_id,
            "selection_token": selection_token,
            "channels": channels,
        }

    async def finalize_channel_selection(
        self,
        account_id: int,
        selection_token: str,
        channel_id: str,
    ) -> Account:
        """Finalize selected YouTube channel and connect account."""
        await self._clear_expired_pending()
        result = await self.db.execute(
            select(YouTubeOAuthPending).where(
                YouTubeOAuthPending.account_id == account_id,
                YouTubeOAuthPending.selection_token == selection_token,
            )
        )
        pending = result.scalar_one_or_none()
        if not pending:
            raise ValueError("Channel selection has expired. Please reconnect the account.")

        try:
            channels = json.loads(pending.channels_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Pending channel selection is corrupted. Please reconnect.") from exc

        selected = None
        for channel in channels:
            if channel.get("channel_id") == channel_id:
                selected = channel
                break
        if not selected:
            raise ValueError("Selected channel is not available for this OAuth session.")

        token_data = {
            "access_token": pending.access_token,
            "refresh_token": pending.refresh_token,
            "expires_in": max(
                60,
                int((pending.token_expires_at - datetime.utcnow()).total_seconds())
            ) if pending.token_expires_at else 3600,
        }

        account = await self._persist_connected_account(
            account_id=account_id,
            token_data=token_data,
            channel=YouTubeChannel(
                channel_id=selected["channel_id"],
                title=selected["title"],
                handle=selected["handle"],
            ),
        )

        await self.db.delete(pending)
        await self.db.flush()
        return account
    
    async def upload_video(
        self,
        account_id: int,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",  # private, public, unlisted
        made_for_kids: bool = False,
        progress_callback=None,
    ) -> UploadResult:
        """
        Upload a video to YouTube.
        
        Args:
            account_id: Account to upload to
            video_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description
            tags: Video tags
            privacy_status: Video privacy (private, public, unlisted)
            made_for_kids: Whether video is made for kids
            progress_callback: Optional progress callback
            
        Returns:
            UploadResult with video ID and URL on success
        """
        account = await self.db.get(Account, account_id)
        if not account:
            return UploadResult(
                success=False,
                platform="youtube_shorts",
                account_id=account_id,
                error=f"Account {account_id} not found"
            )
        
        if account.platform != Platform.YOUTUBE_SHORTS:
            return UploadResult(
                success=False,
                platform="youtube_shorts",
                account_id=account_id,
                error="Account is not a YouTube account"
            )
        
        if account.auth_status != AuthStatus.CONNECTED:
            return UploadResult(
                success=False,
                platform="youtube_shorts",
                account_id=account_id,
                error="Account is not connected - authorization required"
            )
        
        video_path = Path(video_path)
        if not video_path.exists():
            return UploadResult(
                success=False,
                platform="youtube_shorts",
                account_id=account_id,
                error=f"Video file not found: {video_path}"
            )
        
        try:
            # Refresh token if needed
            account = await self.refresh_token_if_needed(account)
            
            # Prepare video metadata
            body = {
                "snippet": {
                    "title": title[:100],  # YouTube max title length
                    "description": description[:5000],  # YouTube max description
                    "tags": tags[:500] if tags else [],  # YouTube max tags
                    "categoryId": "22",  # People & Blogs (common for shorts)
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": made_for_kids,
                    # Mark as Short via description if < 60 seconds
                    # YouTube auto-detects shorts based on aspect ratio and duration
                }
            }
            
            # Upload using YouTube Data API resumable upload
            # In production, use google-api-python-client
            # Step 1: Initiate resumable upload
            file_size = video_path.stat().st_size

            timeout = httpx.Timeout(UPLOAD_HTTP_TIMEOUT_SECONDS, connect=OAUTH_HTTP_TIMEOUT_SECONDS)
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Create upload session
                response = await client.post(
                    "https://www.googleapis.com/upload/youtube/v3/videos"
                    "?uploadType=resumable&part=snippet,status",
                    headers={
                        "Authorization": f"Bearer {account.access_token}",
                        "Content-Type": "application/json",
                        "X-Upload-Content-Length": str(file_size),
                        "X-Upload-Content-Type": "video/mp4",
                    },
                    json=body,
                )
                if response.status_code != 200:
                    return UploadResult(
                        success=False,
                        platform="youtube_shorts",
                        account_id=account_id,
                        error=f"Failed to initiate upload: {_extract_oauth_error_detail(response)}"
                    )

                upload_url = response.headers.get("Location")
                if not upload_url:
                    return UploadResult(
                        success=False,
                        platform="youtube_shorts",
                        account_id=account_id,
                        error="No upload URL received"
                    )
                
                # Step 2: Upload video content
                with open(video_path, "rb") as video_file:
                    video_data = video_file.read()

                response = await client.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(file_size),
                    },
                    content=video_data,
                )
                if response.status_code not in (200, 201):
                    return UploadResult(
                        success=False,
                        platform="youtube_shorts",
                        account_id=account_id,
                        error=f"Failed to upload video: {_extract_oauth_error_detail(response)}"
                    )

                try:
                    result = response.json()
                except ValueError:
                    return UploadResult(
                        success=False,
                        platform="youtube_shorts",
                        account_id=account_id,
                        error="Failed to upload video: invalid provider response"
                    )
            
            video_id = result.get("id")
            video_url = f"https://youtube.com/shorts/{video_id}" if video_id else None
            
            # Update account's last upload time
            account.last_upload_at = datetime.utcnow()
            await self.db.flush()
            
            return UploadResult(
                success=True,
                platform="youtube_shorts",
                account_id=account_id,
                video_id=video_id,
                video_url=video_url,
            )
            
        except Exception as e:
            return UploadResult(
                success=False,
                platform="youtube_shorts",
                account_id=account_id,
                error=str(e)
            )


class UploadService:
    """
    Unified upload service for all platforms.
    
    Routes uploads to platform-specific services.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._youtube = YouTubeUploadService(db)
    
    async def create_upload_job(
        self,
        project_id: int,
        video_path: str,
        account_id: int,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",
    ) -> Job:
        """Create an upload job for tracking."""
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        job_metadata = {
            "video_path": video_path,
            "account_id": account_id,
            "platform": account.platform.value,
            "title": title,
            "description": description,
            "tags": tags or [],
            "privacy_status": privacy_status,
        }
        
        job = Job(
            project_id=project_id,
            job_type=JobType.UPLOAD,
            status=JobStatus.PENDING,
            message=f"Preparing upload to {account.platform.value}...",
            result=json.dumps(job_metadata),
        )
        
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        
        return job
    
    async def execute_upload(
        self,
        account_id: int,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",
        progress_callback=None,
    ) -> UploadResult:
        """
        Execute upload to a platform.
        
        Routes to appropriate platform service based on account.
        """
        account = await self.db.get(Account, account_id)
        if not account:
            return UploadResult(
                success=False,
                platform="unknown",
                account_id=account_id,
                error=f"Account {account_id} not found"
            )
        
        if account.platform == Platform.YOUTUBE_SHORTS:
            return await self._youtube.upload_video(
                account_id=account_id,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy_status,
                progress_callback=progress_callback,
            )
        
        # Other platforms return not-implemented for now
        return UploadResult(
            success=False,
            platform=account.platform.value,
            account_id=account_id,
            error=f"Direct upload not yet implemented for {account.platform.value}. "
                  f"Use the exported video and metadata.json for manual upload."
        )
    
    async def get_oauth_url(self, account_id: int, redirect_uri: str) -> Dict[str, Any]:
        """Get OAuth URL for a platform account."""
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        if account.platform == Platform.YOUTUBE_SHORTS:
            url = await self._youtube.get_oauth_url(account_id, redirect_uri)
            return {"url": url, "platform": "youtube_shorts"}
        
        raise ValueError(f"OAuth not implemented for {account.platform.value}")
    
    async def complete_oauth(
        self,
        account_id: int,
        authorization_code: str,
        redirect_uri: str,
    ) -> Dict[str, Any]:
        """Complete OAuth flow for a platform account."""
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        if account.platform == Platform.YOUTUBE_SHORTS:
            result = await self._youtube.complete_oauth(
                account_id, authorization_code, redirect_uri
            )
            if result.status == "connected":
                return {"status": "connected", "account": result.account}
            return {
                "status": "selection_required",
                "account_id": result.account_id,
                "selection_token": result.selection_token,
                "channels": [c.to_dict() for c in result.channels or []],
            }
        
        raise ValueError(f"OAuth not implemented for {account.platform.value}")

    async def get_pending_youtube_channels(
        self,
        account_id: int,
        selection_token: str,
    ) -> Dict[str, Any]:
        """Get pending YouTube channel options."""
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if account.platform != Platform.YOUTUBE_SHORTS:
            raise ValueError("Account is not a YouTube account")
        return await self._youtube.get_pending_channels(account_id, selection_token)

    async def finalize_youtube_channel_selection(
        self,
        account_id: int,
        selection_token: str,
        channel_id: str,
    ) -> Account:
        """Finalize YouTube channel selection for pending OAuth session."""
        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if account.platform != Platform.YOUTUBE_SHORTS:
            raise ValueError("Account is not a YouTube account")
        return await self._youtube.finalize_channel_selection(
            account_id=account_id,
            selection_token=selection_token,
            channel_id=channel_id,
        )

    async def upload_selected_clips(
        self,
        project_id: int,
        clip_ids: List[int],
        account_id: int,
        niche_id: int,
        privacy_status: str = "private",
        title_prefix: Optional[str] = None,
        description_template: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        use_vertical_preset: bool = True,
        vertical_framing: Optional[str] = None,
        vertical_resolution: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create one upload job per selected clip and enqueue direct upload."""
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        if not project.source_path:
            raise ValueError("Project has no source video path")

        account = await self.db.get(Account, account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if account.platform != Platform.YOUTUBE_SHORTS:
            raise ValueError("Selected account is not a YouTube Shorts account")
        if account.auth_status != AuthStatus.CONNECTED:
            raise ValueError("YouTube account is not connected")
        if not account.platform_user_id:
            raise ValueError("This YouTube account must be reconnected to select a channel before direct uploads.")
        if account.niche_id != niche_id:
            raise ValueError("Selected account does not belong to the selected niche")

        niche = await self.db.get(Niche, niche_id)
        if not niche:
            raise ValueError(f"Niche {niche_id} not found")

        result = await self.db.execute(
            select(Clip).where(Clip.project_id == project_id, Clip.id.in_(clip_ids))
        )
        clips = list(result.scalars().all())
        clips_by_id = {clip.id: clip for clip in clips}

        jobs: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        hashtags_list = hashtags or []
        if niche.default_hashtags:
            try:
                hashtags_list = list(set(hashtags_list + json.loads(niche.default_hashtags)))
            except json.JSONDecodeError:
                pass
        hashtag_text = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags_list)
        description_base = description_template or niche.default_caption_template or ""

        temp_root = settings.data_dir / "temp_uploads" / str(project_id)
        temp_root.mkdir(parents=True, exist_ok=True)

        from app.workers.handlers import run_upload_job
        import asyncio

        for clip_id in clip_ids:
            clip = clips_by_id.get(clip_id)
            if not clip:
                errors.append({"clip_id": clip_id, "error": "Clip not found in project"})
                continue
            if clip.duration > 60:
                errors.append({"clip_id": clip_id, "error": f"Clip duration {clip.duration:.1f}s exceeds YouTube Shorts max 60s"})
                continue
            if clip.duration < 1:
                errors.append({"clip_id": clip_id, "error": "Clip duration is too short for upload"})
                continue

            safe_clip_name = clip.name or f"Clip {clip.ordering + 1}"
            filename_base = "".join(c for c in safe_clip_name if c.isalnum() or c in (" ", "-", "_")).strip()
            if not filename_base:
                filename_base = f"clip_{clip.id}"
            output_path = temp_root / f"{filename_base}_{clip.id}.mp4"

            preset = ExportPreset.vertical() if use_vertical_preset else ExportPreset.original()
            await export_clip_enhanced(
                source_path=project.source_path,
                output_path=output_path,
                start_time=clip.start_time,
                end_time=clip.end_time,
                preset=preset,
                vertical_framing=vertical_framing or settings.vertical_framing,
                vertical_resolution=vertical_resolution or settings.vertical_resolution,
            )

            title = safe_clip_name[:100]
            if title_prefix:
                title = f"{title_prefix.strip()} {title}".strip()[:100]
            description_parts = [description_base.strip()] if description_base else []
            if hashtag_text:
                description_parts.append(hashtag_text)
            description = "\n\n".join(p for p in description_parts if p)[:5000]

            job = await self.create_upload_job(
                project_id=project_id,
                video_path=str(output_path),
                account_id=account_id,
                title=title,
                description=description,
                tags=hashtags_list,
                privacy_status=privacy_status,
            )

            metadata = json.loads(job.result) if job.result else {}
            metadata["clip_id"] = clip.id
            metadata["delete_after_upload"] = True
            metadata["temp_video_path"] = str(output_path)
            metadata["use_vertical_preset"] = use_vertical_preset
            metadata["vertical_framing"] = vertical_framing or settings.vertical_framing
            metadata["vertical_resolution"] = vertical_resolution or settings.vertical_resolution
            job.result = json.dumps(metadata)
            await self.db.flush()

            asyncio.create_task(run_upload_job(job.id))
            jobs.append({"job_id": job.id, "clip_id": clip.id, "clip_name": safe_clip_name})

        return {"jobs": jobs, "errors": errors}
