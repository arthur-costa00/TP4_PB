from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator
from .models import Correction

class ErrorInfo(BaseModel):
    code: str
    message: str

class Accepted(BaseModel):
    task_id: str
    status: Literal["pending"] = "pending"
    status_url: str

class TaskStatus(BaseModel):
    model_config=ConfigDict(extra="forbid")
    task_id: str
    status: Literal["pending","done","error"]
    result: Correction | None = None
    error: ErrorInfo | None = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def coherent(self):
        if self.status=="done" and (self.result is None or self.error is not None):
            raise ValueError("done exige result e não admite error")
        if self.status=="error" and (self.error is None or self.result is not None):
            raise ValueError("error exige error e não admite result")
        if self.status=="pending" and (self.error is not None or self.result is not None):
            raise ValueError("pending não admite result/error")
        return self
