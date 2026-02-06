"""Temporary storage for pending YouTube OAuth channel selection."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class YouTubeOAuthPending(Base):
    """Stores temporary OAuth tokens and channel choices until user selects a channel."""

    __tablename__ = "youtube_oauth_pending"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    selection_token = Column(String(255), nullable=False, unique=True, index=True)

    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    channels_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    account = relationship("Account")

