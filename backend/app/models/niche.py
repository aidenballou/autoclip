"""Niche model for organizing accounts by content category."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Niche(Base):
    """Niche model representing a content category/focus area."""
    
    __tablename__ = "niches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Default settings for clips in this niche
    default_hashtags = Column(Text, nullable=True)  # JSON array stored as text
    default_caption_template = Column(Text, nullable=True)
    
    # Default overlay settings
    default_text_overlay = Column(Text, nullable=True)  # Default text to overlay
    default_text_position = Column(String(32), default="bottom")  # top, center, bottom
    default_text_color = Column(String(32), default="#FFFFFF")
    default_text_size = Column(Integer, default=48)
    
    # Default background audio
    default_audio_path = Column(String(4096), nullable=True)
    default_audio_volume = Column(Integer, default=30)  # 0-100
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    accounts = relationship("Account", back_populates="niche", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Niche(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        """Convert to dictionary."""
        import json
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_hashtags": json.loads(self.default_hashtags) if self.default_hashtags else [],
            "default_caption_template": self.default_caption_template,
            "default_text_overlay": self.default_text_overlay,
            "default_text_position": self.default_text_position,
            "default_text_color": self.default_text_color,
            "default_text_size": self.default_text_size,
            "default_audio_path": self.default_audio_path,
            "default_audio_volume": self.default_audio_volume,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
