
from typing import Optional

from .request import TranscriptionRequest


class Task:
    PENDING = "PENDING"
    COMPLETED = "SUCCESS"
    STARTED = "STARTED"
    FAILED = "FAILURE"

    def __init__(self, task_id: str, request: TranscriptionRequest):
        self.task_id = task_id
        self.request = request
        self.state = self.PENDING
        self.result: Optional[bytes] = None
        self.error: Optional[str] = None

    def set_in_progress(self):
        self.state = self.STARTED

    def set_completed(self, result: bytes):
        self.state = self.COMPLETED
        self.result = result

    def set_failed(self, error: str):
        self.state = self.FAILED
        self.error = error
