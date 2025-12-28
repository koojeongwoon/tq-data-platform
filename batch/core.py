
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

# Setup basic logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JobContext:
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.status = "PENDING"
        self.start_time = None
        self.end_time = None

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

class Step(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, context: JobContext):
        """
        Execute the step logic.
        Raises Exception on failure.
        """
        pass

class Job:
    def __init__(self, name: str, steps: List[Step]):
        self.name = name
        self.steps = steps

    def run(self):
        context = JobContext()
        context.start_time = datetime.now()
        context.status = "RUNNING"
        
        logger.info(f"--- Starting Job: {self.name} ---")

        try:
            for step in self.steps:
                logger.info(f"Starting Step: {step.name}")
                step.execute(context)
                logger.info(f"Finished Step: {step.name}")
            
            context.status = "COMPLETED"
            logger.info(f"--- Job Completed : {self.name} ---")
            
        except Exception as e:
            context.status = "FAILED"
            logger.error(f"Job Failed at Step: {step.name if 'step' in locals() else 'Unknown'}")
            logger.error(f"Error: {e}")
            raise
        finally:
            context.end_time = datetime.now()
            duration = context.end_time - context.start_time
            logger.info(f"Duration: {duration}")

        return context
