# backend/jobs.py
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Literal
import uuid
import threading

Status = Literal["queued", "processing", "done", "error"]

class JobManager:
    def __init__(self, max_workers: int = 1):
        self.exec = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()
        self.jobs: Dict[str, Dict] = {}

    def submit(self, func, *args, **kwargs) -> str:
        job_id = uuid.uuid4().hex
        with self.lock:
            self.jobs[job_id] = {"status": "queued", "progress": 0, "error": None, "result": None}
        def wrapper():
            self.update(job_id, status="processing", progress=5)
            try:
                result = func(job_id, self.update, *args, **kwargs)
                self.update(job_id, status="done", progress=100, result=result)
            except Exception as e:
                self.update(job_id, status="error", error=str(e), progress=100)
        self.exec.submit(wrapper)
        return job_id

    def update(self, job_id: str, *, status: Status = None, progress: int = None, error: str = None, result=None):
        with self.lock:
            data = self.jobs.get(job_id, {})
            if status: data["status"] = status
            if progress is not None: data["progress"] = progress
            if error is not None: data["error"] = error
            if result is not None: data["result"] = result
            self.jobs[job_id] = data

    def get(self, job_id: str) -> Dict:
        with self.lock:
            return self.jobs.get(job_id, None)
