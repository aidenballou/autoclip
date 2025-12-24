"""Background job runner using asyncio."""
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Callable, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)


class JobRunner:
    """Async background job runner."""
    
    def __init__(self):
        self._running_jobs: Dict[int, asyncio.Task] = {}
        self._job_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a job type."""
        self._job_handlers[job_type] = handler
    
    async def start_job(
        self,
        job_id: int,
        job_type: str,
        **kwargs
    ) -> bool:
        """
        Start a background job.
        
        Args:
            job_id: Database ID of the job
            job_type: Type of job to run
            **kwargs: Arguments to pass to the job handler
            
        Returns:
            True if job started successfully
        """
        if job_id in self._running_jobs:
            logger.warning(f"Job {job_id} is already running")
            return False
        
        handler = self._job_handlers.get(job_type)
        if not handler:
            logger.error(f"No handler registered for job type: {job_type}")
            return False
        
        # Create task
        task = asyncio.create_task(
            self._run_job(job_id, handler, **kwargs)
        )
        self._running_jobs[job_id] = task
        
        return True
    
    async def _run_job(
        self,
        job_id: int,
        handler: Callable,
        **kwargs
    ):
        """Run a job with error handling and status updates."""
        try:
            async with async_session_maker() as session:
                # Update job to running
                job = await session.get(Job, job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return
                
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                job.message = "Starting..."
                await session.commit()
            
            # Create progress callback
            async def update_progress(progress: float, message: str = None):
                async with async_session_maker() as session:
                    job = await session.get(Job, job_id)
                    if job:
                        job.progress = min(100, max(0, progress))
                        if message:
                            job.message = message
                        await session.commit()
            
            # Run the handler
            result = await handler(
                job_id=job_id,
                progress_callback=update_progress,
                **kwargs
            )
            
            # Update job to completed
            async with async_session_maker() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                    job.message = "Completed successfully"
                    job.completed_at = datetime.utcnow()
                    if result:
                        import json
                        job.result = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    await session.commit()
            
            logger.info(f"Job {job_id} completed successfully")
            
        except asyncio.CancelledError:
            async with async_session_maker() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatus.CANCELLED
                    job.message = "Job cancelled"
                    job.completed_at = datetime.utcnow()
                    await session.commit()
            logger.info(f"Job {job_id} was cancelled")
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            logger.error(f"Job {job_id} failed: {error_msg}\n{error_trace}")
            
            async with async_session_maker() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = JobStatus.FAILED
                    job.message = f"Failed: {error_msg}"
                    job.error = error_trace
                    job.completed_at = datetime.utcnow()
                    await session.commit()
        
        finally:
            # Remove from running jobs
            self._running_jobs.pop(job_id, None)
    
    async def cancel_job(self, job_id: int) -> bool:
        """Cancel a running job."""
        task = self._running_jobs.get(job_id)
        if task:
            task.cancel()
            return True
        return False
    
    def is_job_running(self, job_id: int) -> bool:
        """Check if a job is currently running."""
        return job_id in self._running_jobs
    
    async def shutdown(self):
        """Cancel all running jobs."""
        for job_id, task in self._running_jobs.items():
            task.cancel()
        
        if self._running_jobs:
            await asyncio.gather(
                *self._running_jobs.values(),
                return_exceptions=True
            )
        
        self._running_jobs.clear()


# Global job runner instance
job_runner = JobRunner()

