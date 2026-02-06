"""Niche and Account service for managing content niches and social media accounts."""
import json
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.niche import Niche
from app.models.account import Account, Platform, AuthStatus


class NicheService:
    """Service for managing niches and accounts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # =========================================================================
    # Niche Operations
    # =========================================================================
    
    async def create_niche(
        self,
        name: str,
        description: Optional[str] = None,
        default_hashtags: Optional[List[str]] = None,
        default_caption_template: Optional[str] = None,
        default_text_overlay: Optional[str] = None,
        default_text_position: Optional[str] = None,
        default_text_color: Optional[str] = None,
        default_text_size: Optional[int] = None,
        default_audio_path: Optional[str] = None,
        default_audio_volume: Optional[int] = None,
    ) -> Niche:
        """Create a new niche."""
        # Check for duplicate name
        result = await self.db.execute(
            select(Niche).where(Niche.name == name)
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Niche with name '{name}' already exists")
        
        niche = Niche(
            name=name,
            description=description,
            default_hashtags=json.dumps(default_hashtags) if default_hashtags else None,
            default_caption_template=default_caption_template,
            default_text_overlay=default_text_overlay,
            default_text_position=default_text_position or "bottom",
            default_text_color=default_text_color or "#FFFFFF",
            default_text_size=default_text_size or 48,
            default_audio_path=default_audio_path,
            default_audio_volume=default_audio_volume if default_audio_volume is not None else 30,
        )
        
        self.db.add(niche)
        await self.db.flush()
        await self.db.refresh(niche)
        
        return niche
    
    async def get_niche(self, niche_id: int) -> Optional[Niche]:
        """Get a niche by ID."""
        result = await self.db.execute(
            select(Niche)
            .options(selectinload(Niche.accounts))
            .where(Niche.id == niche_id)
        )
        return result.scalar_one_or_none()
    
    async def list_niches(self) -> List[Niche]:
        """List all niches."""
        result = await self.db.execute(
            select(Niche)
            .options(selectinload(Niche.accounts))
            .order_by(Niche.name)
        )
        return list(result.scalars().all())
    
    async def update_niche(
        self,
        niche_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        default_hashtags: Optional[List[str]] = None,
        default_caption_template: Optional[str] = None,
        default_text_overlay: Optional[str] = None,
        default_text_position: Optional[str] = None,
        default_text_color: Optional[str] = None,
        default_text_size: Optional[int] = None,
        default_audio_path: Optional[str] = None,
        default_audio_volume: Optional[int] = None,
    ) -> Niche:
        """Update a niche."""
        niche = await self.get_niche(niche_id)
        if not niche:
            raise ValueError(f"Niche with ID {niche_id} not found")
        
        # Check for duplicate name if changing
        if name and name != niche.name:
            result = await self.db.execute(
                select(Niche).where(Niche.name == name)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Niche with name '{name}' already exists")
            niche.name = name
        
        if description is not None:
            niche.description = description
        if default_hashtags is not None:
            niche.default_hashtags = json.dumps(default_hashtags)
        if default_caption_template is not None:
            niche.default_caption_template = default_caption_template
        if default_text_overlay is not None:
            niche.default_text_overlay = default_text_overlay
        if default_text_position is not None:
            niche.default_text_position = default_text_position
        if default_text_color is not None:
            niche.default_text_color = default_text_color
        if default_text_size is not None:
            niche.default_text_size = default_text_size
        if default_audio_path is not None:
            niche.default_audio_path = default_audio_path
        if default_audio_volume is not None:
            niche.default_audio_volume = default_audio_volume
        
        await self.db.flush()
        await self.db.refresh(niche)
        
        return niche
    
    async def delete_niche(self, niche_id: int) -> bool:
        """Delete a niche and all associated accounts."""
        niche = await self.get_niche(niche_id)
        if not niche:
            return False
        
        await self.db.delete(niche)
        await self.db.flush()
        
        return True
    
    # =========================================================================
    # Account Operations
    # =========================================================================
    
    async def create_account(
        self,
        niche_id: int,
        platform: str,
        handle: str,
        display_name: Optional[str] = None,
        auto_upload: bool = False,
    ) -> Account:
        """Create a new account for a niche."""
        # Verify niche exists
        niche = await self.get_niche(niche_id)
        if not niche:
            raise ValueError(f"Niche with ID {niche_id} not found")
        
        # Validate platform
        try:
            platform_enum = Platform(platform)
        except ValueError:
            valid_platforms = [p.value for p in Platform]
            raise ValueError(f"Invalid platform '{platform}'. Must be one of: {valid_platforms}")
        
        # Check for duplicate account (same niche + platform + handle)
        result = await self.db.execute(
            select(Account).where(
                Account.niche_id == niche_id,
                Account.platform == platform_enum,
                Account.handle == handle,
            )
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Account {handle} on {platform} already exists in this niche")
        
        account = Account(
            niche_id=niche_id,
            platform=platform_enum,
            handle=handle,
            display_name=display_name,
            auto_upload=auto_upload,
        )
        
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        
        return account
    
    async def get_account(self, account_id: int) -> Optional[Account]:
        """Get an account by ID."""
        result = await self.db.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()
    
    async def list_accounts(self, niche_id: Optional[int] = None) -> List[Account]:
        """List accounts, optionally filtered by niche."""
        query = select(Account).order_by(Account.platform, Account.handle)
        
        if niche_id is not None:
            query = query.where(Account.niche_id == niche_id)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_account(
        self,
        account_id: int,
        handle: Optional[str] = None,
        display_name: Optional[str] = None,
        auto_upload: Optional[bool] = None,
    ) -> Account:
        """Update an account."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        if handle is not None:
            account.handle = handle
        if display_name is not None:
            account.display_name = display_name
        if auto_upload is not None:
            account.auto_upload = auto_upload
        
        await self.db.flush()
        await self.db.refresh(account)
        
        return account
    
    async def delete_account(self, account_id: int) -> bool:
        """Delete an account."""
        account = await self.get_account(account_id)
        if not account:
            return False
        
        await self.db.delete(account)
        await self.db.flush()
        
        return True
    
    async def update_account_auth(
        self,
        account_id: int,
        auth_status: AuthStatus,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at=None,
        platform_user_id: Optional[str] = None,
    ) -> Account:
        """Update account authentication status and tokens."""
        account = await self.get_account(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        account.auth_status = auth_status
        if access_token is not None:
            account.access_token = access_token
        if refresh_token is not None:
            account.refresh_token = refresh_token
        if token_expires_at is not None:
            account.token_expires_at = token_expires_at
        if platform_user_id is not None:
            account.platform_user_id = platform_user_id
        
        await self.db.flush()
        await self.db.refresh(account)
        
        return account
    
    async def get_accounts_for_publishing(
        self,
        niche_id: int,
        platforms: Optional[List[str]] = None,
    ) -> List[Account]:
        """Get connected accounts for a niche that are ready for publishing."""
        query = (
            select(Account)
            .where(
                Account.niche_id == niche_id,
                Account.auth_status == AuthStatus.CONNECTED,
            )
        )
        
        if platforms:
            platform_enums = [Platform(p) for p in platforms]
            query = query.where(Account.platform.in_(platform_enums))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
