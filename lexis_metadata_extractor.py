"""Legacy entrypoint for metadata ingestion.

Use the API in app/main.py for production workloads.
"""

import argparse

from app.services.ingest_service import IngestService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', required=True, help='PDF filename inside data directory')
    parser.add_argument('--start-page', required=True, type=int, help='1-based page number')
    args = parser.parse_args()

    service = IngestService()
    result = service.ingest_metadata(args.pdf, args.start_page)
    print(result)


if __name__ == '__main__':
    main()
