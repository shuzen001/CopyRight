from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    pdf_filename: str = Field(..., description='PDF filename under data directory')


class MetadataParseRequest(ParseRequest):
    start_page: int = Field(..., ge=1, description='1-based start page')


class ParseResponse(BaseModel):
    inserted: int
    collection: str
    sample: Optional[Dict[str, Any]] = None


class BatchResponse(BaseModel):
    total_pdfs: int
    total_inserted: int
    by_file: Dict[str, int]


class HealthResponse(BaseModel):
    status: str


class OpinionLink(BaseModel):
    raw_text: str
    link: str


class OpinionRecord(BaseModel):
    pdf: str
    opinion_id: int
    start_page: int
    end_page: int
    content: str
    urls_dic: List[OpinionLink]
