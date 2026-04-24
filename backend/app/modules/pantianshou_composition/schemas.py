from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    task_id: str
    status: str
    status_url: str
    file_name: str | None = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    stage: str
    stage_text: str
    message: str = ""
    eta_seconds: int | None = None
    eta_confidence: float | None = None
    queue_eta_seconds: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class TaskHistoryItem(BaseModel):
    task_id: str
    status: str
    created_at: str
    original_url: str
    status_url: str
    report_url: str | None = None
    pdf_url: str | None = None
    file_name: str | None = None


class TaskHistoryResponse(BaseModel):
    items: list[TaskHistoryItem]


class FeedbackRequest(BaseModel):
    task_id: str
    rating: int = Field(ge=1, le=5)
    comments: str = ""


class SimpleSuccessResponse(BaseModel):
    success: bool = True


class IngestRulesRequest(BaseModel):
    pan_md_path: str = "pan.md"
    recreate: bool = False
    ruleset_version: str = ""


class IngestStartResponse(BaseModel):
    task_id: str
    status: str
    status_url: str


class IngestTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    stage: str
    message: str = ""
    result: dict | None = None
    error_message: str | None = None


class KnowledgeUploadResponse(BaseModel):
    file_name: str
    stored_url: str
    stored_path: str
