from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    error_message = Column(String, nullable=True)

    results = relationship("ExtractionResult", back_populates="task")

class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(Integer, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    filename = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(TaskStatus))
    error_message = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)

    task = relationship("Task", back_populates="results")

# Database initialization
DATABASE_URL = "sqlite:///./extraction.db"
engine = create_engine(DATABASE_URL)

def init_db():
    Base.metadata.create_all(engine) 