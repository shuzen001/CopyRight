from fastapi import FastAPI, HTTPException

from app.schemas import BatchResponse, HealthResponse, MetadataParseRequest, ParseRequest, ParseResponse
from app.services.ingest_service import IngestService

app = FastAPI(title='CopyRight Ingestion API', version='1.0.0')
service = IngestService()


@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok')


@app.post('/api/metadata/ingest', response_model=ParseResponse)
def ingest_metadata(payload: MetadataParseRequest) -> ParseResponse:
    try:
        return ParseResponse(**service.ingest_metadata(payload.pdf_filename, payload.start_page))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/footnotes/ingest', response_model=ParseResponse)
def ingest_footnotes(payload: ParseRequest) -> ParseResponse:
    try:
        return ParseResponse(**service.ingest_footnotes(payload.pdf_filename))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/api/opinions/ingest', response_model=ParseResponse)
def ingest_opinions(payload: ParseRequest) -> ParseResponse:
    try:
        return ParseResponse(**service.ingest_opinions(payload.pdf_filename))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post('/api/footnotes/ingest-all', response_model=BatchResponse)
def ingest_all_footnotes() -> BatchResponse:
    return BatchResponse(**service.ingest_all_footnotes())
