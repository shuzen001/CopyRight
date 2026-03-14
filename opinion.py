"""Legacy entrypoint for opinion ingestion.

Use the API in app/main.py for production workloads.
"""

import argparse

from app.services.ingest_service import IngestService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', required=True, help='PDF filename inside data directory')
    args = parser.parse_args()

    service = IngestService()
    result = service.ingest_opinions(args.pdf)
    print(result)


if __name__ == '__main__':
    main()
