import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 3600  # 1 hour
        
    def create_task(self, task_id: str, files_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a new prediction task"""
        task = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "files_count": len(files_data),
            "processed_count": 0,
            "results": [],
            "error": None
        }
        
        self.tasks[task_id] = task
        logger.info(f"Created task {task_id} with {len(files_data)} files")
        return task
    
    def update_task_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None):
        """Update task status"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status.value
            self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
            if error:
                self.tasks[task_id]["error"] = error
            logger.info(f"Updated task {task_id} status to {status.value}")
    
    def add_result(self, task_id: str, result: Dict[str, Any]):
        """Add a result to the task"""
        if task_id in self.tasks:
            self.tasks[task_id]["results"].append(result)
            self.tasks[task_id]["processed_count"] += 1
            self.tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
            
            # Check if all files are processed
            if self.tasks[task_id]["processed_count"] >= self.tasks[task_id]["files_count"]:
                self.update_task_status(task_id, TaskStatus.COMPLETED)
            
            logger.info(f"Added result to task {task_id}. Progress: {self.tasks[task_id]['processed_count']}/{self.tasks[task_id]['files_count']}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def get_task_results(self, task_id: str) -> List[Dict[str, Any]]:
        """Get task results"""
        task = self.tasks.get(task_id)
        return task["results"] if task else []
    
    async def cleanup_old_tasks(self):
        """Remove old completed/failed tasks"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            task_time = datetime.fromisoformat(task["updated_at"])
            if (task_time < cutoff_time and 
                task["status"] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            logger.info(f"Cleaned up old task: {task_id}")
    
    async def start_cleanup_scheduler(self):
        """Start background task to cleanup old tasks"""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            await self.cleanup_old_tasks()

# Global instance
task_manager = TaskManager()