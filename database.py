from sqlalchemy.orm import sessionmaker
from models import engine, Task, ExtractionResult, TaskStatus
from contextlib import contextmanager
import uuid

Session = sessionmaker(bind=engine)

@contextmanager
def get_db():
    db = Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def create_task(total_files: int) -> str:
    """Create a new task and return its ID"""
    task_id = str(uuid.uuid4())
    with get_db() as db:
        task = Task(
            id=task_id,
            total_files=total_files,
            status=TaskStatus.PENDING
        )
        db.add(task)
    return task_id

def update_task_status(task_id: str, status: TaskStatus, error_message: str = None):
    """Update task status and error message"""
    with get_db() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            if error_message:
                task.error_message = error_message

def increment_processed_files(task_id: str, success: bool = True):
    """Increment processed or failed files count"""
    with get_db() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            if success:
                task.processed_files += 1
            else:
                task.failed_files += 1
            
            # Update task status if all files are processed
            total_processed = task.processed_files + task.failed_files
            if total_processed == task.total_files:
                if task.failed_files == task.total_files:
                    task.status = TaskStatus.FAILED
                elif task.failed_files > 0:
                    task.status = TaskStatus.COMPLETED
                else:
                    task.status = TaskStatus.COMPLETED

def add_extraction_result(
    task_id: str,
    filename: str,
    status: TaskStatus,
    extracted_data: dict = None,
    error_message: str = None
):
    """Add extraction result for a file"""
    with get_db() as db:
        result = ExtractionResult(
            task_id=task_id,
            filename=filename,
            status=status,
            extracted_data=extracted_data,
            error_message=error_message
        )
        db.add(result)

def get_task_status(task_id: str) -> dict:
    """Get task status and progress"""
    with get_db() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        return {
            "id": task.id,
            "status": task.status.value,
            "total_files": task.total_files,
            "processed_files": task.processed_files,
            "failed_files": task.failed_files,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }

def get_task_results(task_id: str) -> list:
    """Get all extraction results for a task"""
    with get_db() as db:
        results = db.query(ExtractionResult).filter(
            ExtractionResult.task_id == task_id
        ).all()
        
        return [{
            "filename": result.filename,
            "status": result.status.value,
            "error_message": result.error_message,
            "extracted_data": result.extracted_data,
            "created_at": result.created_at.isoformat()
        } for result in results] 