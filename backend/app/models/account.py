"""Account model for social media platform connections."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Platform(str, enum.Enum):
    """Supported social media platforms."""
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    TWITTER = "twitter"
    SNAPCHAT = "snapchat"


class AuthStatus(str, enum.Enum):
    """Account authentication status."""
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    EXPIRED = "expired"
    ERROR = "error"


class Account(Base):
    """Account model representing a social media account linked to a niche."""
    
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    niche_id = Column(Integer, ForeignKey("niches.id", ondelete="CASCADE"), nullable=False)
    
    # Platform details
    platform = Column(Enum(Platform), nullable=False)
    handle = Column(String(255), nullable=False)  # @username or channel name
    display_name = Column(String(255), nullable=True)
    
    # Authentication
    auth_status = Column(Enum(AuthStatus), default=AuthStatus.NOT_CONNECTED, nullable=False)
    access_token = Column(Text, nullable=True)  # Encrypted in production
    refresh_token = Column(Text, nullable=True)  # Encrypted in production
    token_expires_at = Column(DateTime, nullable=True)
    
    # Platform-specific settings
    platform_user_id = Column(String(255), nullable=True)  # Platform's user ID
    
    # Upload preferences for this account
    auto_upload = Column(Boolean, default=False)  # Auto-upload when publishing
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_upload_at = Column(DateTime, nullable=True)
    
    # Relationships
    niche = relationship("Niche", back_populates="accounts")
    
    def __repr__(self):
        return f"<Account(id={self.id}, platform={self.platform}, handle='{self.handle}')>"
    
    def to_dict(self):
        """Convert to dictionary (excludes sensitive auth data)."""
        return {
            "id": self.id,
            "niche_id": self.niche_id,
            "platform": self.platform.value,
            "handle": self.handle,
            "display_name": self.display_name,
            "auth_status": self.auth_status.value,
            "platform_user_id": self.platform_user_id,
            "auto_upload": self.auto_upload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_upload_at": self.last_upload_at.isoformat() if self.last_upload_at else None,
        }
