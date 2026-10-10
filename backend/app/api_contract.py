"""
API contract for the ingestion API (v1).
Every endpoint should use these models as response_model so the
OpenAPI docs show exact shapes for the frontend.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class DocType(str, Enum):
    transcript = "transcript"
    form_10k = "10-K"
    form_10q = "10-Q"
    news = "news"
    commentary = "commentary"


class DocStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    chunking = "chunking"
    indexed = "indexed"
    failed = "failed"


class UploadResponse(BaseModel):
    document_id: int = Field(..., examples=[12])
    filename: str = Field(..., examples=["NVDA_Q2_FY26_call.pdf"])
    doc_type: DocType
    status: DocStatus
    duplicate: bool = Field(
        False,
        description="True if an identical file (same hash) was already ingested; "
                    "the existing document_id is returned instead of creating a new one.",
    )


class DocumentOut(BaseModel):
    document_id: int
    filename: str
    company: Optional[str] = Field(None, examples=["NVIDIA"])
    quarter: Optional[str] = Field(None, examples=["Q2 FY26"])
    doc_type: DocType
    status: DocStatus
    chunk_count: int = 0
    error_message: Optional[str] = Field(None, description="Only set when status is 'failed'.")
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class ErrorBody(BaseModel):
    code: str = Field(..., examples=["unsupported_file_type"])
    message: str = Field(..., examples=["Only PDF, TXT and HTML files are supported."])


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Raise this anywhere in the backend instead of HTTPException."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


# Error codes:
#   400 empty_file | 404 document_not_found | 413 file_too_large
#   415 unsupported_file_type | 422 invalid_request | 500 internal_error


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request", "message": str(exc.errors()[0]["msg"])}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Something went wrong on our side."}},
        )
