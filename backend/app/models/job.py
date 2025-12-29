"""Job model for tracking background tasks."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class JobType(str, enum.Enum):
    """Job type enumeration."""
    DOWNLOAD = "download"
    ANALYZE = "analyze"
    THUMBNAIL = "thumbnail"
    EXPORT = "export"
    EXPORT_BATCH = "export_batch"


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Job model for tracking background tasks."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Job info
    job_type = Column(Enum(JobType), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    
    # Progress tracking
    progress = Column(Float, default=0.0, nullable=False)  # 0.0 to 100.0
    message = Column(String(1024), nullable=True)
    
    # Results/errors
    result = Column(Text, nullable=True)  # JSON string for results
    error = Column(Text, nullable=True)
    
    # Log file path
    log_path = Column(String(4096), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="jobs")
    
    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

