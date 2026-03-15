import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.ingest_service import IngestService
from app.config import settings

def process_pdf(filename: str, service: IngestService):
    results = {}
    try:
        # Assuming metadata starts looking at page 0
        meta_res = service.ingest_metadata(filename, start_page=1, collection='TC_index_todo')
        results['metadata'] = meta_res['inserted']
    except Exception as e:
        results['metadata_error'] = str(e)

    try:
        fn_res = service.ingest_footnotes(filename, collection='TC_footNote_testing', index_collection='TC_index_todo')
        results['footnotes'] = fn_res['inserted']
    except Exception as e:
        results['footnotes_error'] = str(e)
        
    return filename, results

def main():
    service = IngestService()
    
    # Get all PDF files
    pdf_files = sorted([f for f in os.listdir(settings.data_dir) if f.lower().endswith('.pdf')])
    print(f"Found {len(pdf_files)} PDF files to process in '{settings.data_dir}'.")

    total_meta = 0
    total_fn = 0
    errors = []

    # Process files (we can do it sequentially so it doesn't overwhelm Mongo/PyMuPDF)
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] Processing {pdf_file} ... ", end="")
        _, results = process_pdf(pdf_file, service)
        
        meta_cnt = results.get('metadata', 0)
        total_meta += meta_cnt
        
        fn_cnt = results.get('footnotes', 0)
        total_fn += fn_cnt
        
        if 'metadata_error' in results or 'footnotes_error' in results:
            err_msg = f"Meta: {results.get('metadata_error', 'OK')}, FN: {results.get('footnotes_error', 'OK')}"
            print(f"ERROR ({err_msg})")
            errors.append((pdf_file, err_msg))
        else:
            print(f"OK (Meta: {meta_cnt}, FN: {fn_cnt})")

    print(f"\n✅ Processing Complete!")
    print(f"Total Metadata Records inserted/updated: {total_meta}")
    print(f"Total Footnote Records inserted/updated: {total_fn}")
    
    if errors:
        print(f"\n⚠️ Encountered {len(errors)} errors:")
        for f, err in errors[:10]:
            print(f"  - {f}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more.")

if __name__ == "__main__":
    main()
