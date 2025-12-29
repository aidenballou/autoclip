"""Compound clip models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class CompoundClip(Base):
    """Compound clip model - a combination of multiple clips."""
    
    __tablename__ = "compound_clips"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="compound_clips")
    items = relationship("CompoundClipItem", back_populates="compound_clip", 
                        cascade="all, delete-orphan", order_by="CompoundClipItem.ordering")
    
    def __repr__(self):
        return f"<CompoundClip(id={self.id}, name='{self.name}')>"
    
    @property
    def total_duration(self):
        """Get total duration of all items."""
        return sum(item.duration for item in self.items)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "total_duration": self.total_duration,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CompoundClipItem(Base):
    """Item in a compound clip."""
    
    __tablename__ = "compound_clip_items"
    
    id = Column(Integer, primary_key=True, index=True)
    compound_clip_id = Column(Integer, ForeignKey("compound_clips.id", ondelete="CASCADE"), nullable=False)
    clip_id = Column(Integer, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    
    # Optional overrides for start/end within the source clip
    start_override = Column(Float, nullable=True)
    end_override = Column(Float, nullable=True)
    
    # Ordering
    ordering = Column(Integer, nullable=False, default=0)
    
    # Relationships
    compound_clip = relationship("CompoundClip", back_populates="items")
    clip = relationship("Clip", back_populates="compound_items")
    
    def __repr__(self):
        return f"<CompoundClipItem(compound={self.compound_clip_id}, clip={self.clip_id}, order={self.ordering})>"
    
    @property
    def start_time(self):
        """Get effective start time."""
        return self.start_override if self.start_override is not None else self.clip.start_time
    
    @property
    def end_time(self):
        """Get effective end time."""
        return self.end_override if self.end_override is not None else self.clip.end_time
    
    @property
    def duration(self):
        """Get duration of this item."""
        return self.end_time - self.start_time
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "compound_clip_id": self.compound_clip_id,
            "clip_id": self.clip_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_override": self.start_override,
            "end_override": self.end_override,
            "duration": self.duration,
            "ordering": self.ordering,
        }

