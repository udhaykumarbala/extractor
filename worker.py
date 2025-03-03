import asyncio
import aiofiles
import os
from typing import List
import logging
import traceback
from database import (
    create_task,
    update_task_status,
    increment_processed_files,
    add_extraction_result,
    TaskStatus
)
from llm_method import llm_extract_data_from_pdf
from datetime import datetime
from fastapi.encoders import jsonable_encoder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExtractionWorker:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        self.tasks = {}
        os.makedirs(upload_dir, exist_ok=True)

    async def save_uploaded_file(self, file_data: bytes, filename: str) -> str:
        """Save uploaded file to disk"""
        filepath = os.path.join(self.upload_dir, filename)
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(file_data)
        return filepath

    async def process_file(self, task_id: str, filepath: str, filename: str):
        """Process a single PDF file"""
        try:
            # Extract data from PDF
            extracted_data = await llm_extract_data_from_pdf(filepath)
            
            # Convert to JSON-serializable format
            try:
                serialized_data = jsonable_encoder(extracted_data)
            except Exception as json_err:
                logger.error(f"Error serializing data for {filename}: {str(json_err)}")
                # Try a more defensive approach to salvage partial data
                try:
                    # Create a filtered dictionary without problematic fields
                    safe_data = {}
                    for key, value in extracted_data.__dict__.items():
                        if key.startswith('_'):
                            continue
                        try:
                            # Test if this field can be serialized
                            jsonable_encoder({key: value})
                            safe_data[key] = value
                        except:
                            safe_data[key] = None
                    
                    serialized_data = jsonable_encoder(safe_data)
                    logger.warning(f"Recovered partial data for {filename} by removing problematic fields")
                except Exception as recovery_err:
                    logger.error(f"Failed to recover any data from {filename}: {str(recovery_err)}")
                    raise ValueError(f"Data serialization failed: {str(json_err)}")
            
            # Add filename to the extracted data
            serialized_data['source_file'] = filename
            
            # Add successful result
            add_extraction_result(
                task_id=task_id,
                filename=filename,
                status=TaskStatus.COMPLETED,
                extracted_data=serialized_data
            )
            increment_processed_files(task_id, success=True)
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing file {filename}: {str(e)}")
            logger.debug(f"Detailed error traceback: {error_details}")
            
            # Add failed result
            add_extraction_result(
                task_id=task_id,
                filename=filename,
                status=TaskStatus.FAILED,
                error_message=str(e)
            )
            increment_processed_files(task_id, success=False)
        
        finally:
            # Clean up uploaded file
            try:
                os.remove(filepath)
            except Exception as e:
                logger.error(f"Error removing file {filepath}: {str(e)}")

    async def process_files(self, task_id: str, files: List[tuple]):
        """Process multiple PDF files for a task"""
        try:
            update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Process files concurrently
            tasks = []
            for file_data, filename in files:
                filepath = await self.save_uploaded_file(file_data, filename)
                task = asyncio.create_task(
                    self.process_file(task_id, filepath, filename)
                )
                tasks.append(task)
            
            # Wait for all files to be processed
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error in task {task_id}: {str(e)}")
            update_task_status(task_id, TaskStatus.FAILED, str(e))

    async def create_extraction_task(self, files: List[tuple]) -> str:
        """Create a new extraction task and start processing files"""
        task_id = create_task(len(files))
        
        # Start processing in background
        asyncio.create_task(self.process_files(task_id, files))
        
        return task_id

# Create global worker instance
worker = ExtractionWorker() 