"""Legacy entrypoint for footnote ingestion.

Use the API in app/main.py for production workloads.
"""

from app.services.ingest_service import IngestService


if __name__ == '__main__':
    service = IngestService()
    result = service.ingest_all_footnotes()
    print(result)
