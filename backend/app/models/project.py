"""Project model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Float
from sqlalchemy.orm import relationship

from app.db.database import Base


class SourceType(str, enum.Enum):
    """Source type enumeration."""
    YOUTUBE = "youtube"
    LOCAL = "local"


class ProjectStatus(str, enum.Enum):
    """Project status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"


class Project(Base):
    """Project model representing a video source and its clips."""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Source information
    source_type = Column(Enum(SourceType), nullable=False)
    source_url = Column(String(2048), nullable=True)  # For YouTube
    source_path = Column(String(4096), nullable=True)  # Local path to video file
    
    # Video metadata
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    video_codec = Column(String(64), nullable=True)
    audio_codec = Column(String(64), nullable=True)
    
    # Status
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PENDING, nullable=False)
    error_message = Column(String(4096), nullable=True)
    
    # Output settings
    output_folder = Column(String(4096), nullable=True)
    
    # Relationships
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    compound_clips = relationship("CompoundClip", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def project_dir(self):
        """Get the project directory path."""
        from app.config import settings
        return settings.projects_dir / str(self.id)
    
    @property
    def source_filename(self):
        """Get the source video filename."""
        if self.source_path:
            from pathlib import Path
            return Path(self.source_path).name
        return None

