import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor
from app.services.ingest_service import IngestService
from app.config import settings

def process_pdf(filename: str, service: IngestService):
    """Processes a single PDF through Phase 1: Metadata, Footnotes, Opinions."""
    results = {}
    
    # 1. Metadata
    try:
        meta_res = service.ingest_metadata(filename, start_page=1, collection='TC_index_todo')
        results['metadata'] = meta_res.get('inserted', 0)
    except Exception as e:
        results['metadata_error'] = str(e)

    # 2. Footnotes
    try:
        fn_res = service.ingest_footnotes(filename, collection='TC_footNote_testing', index_collection='TC_index_todo')
        results['footnotes'] = fn_res.get('inserted', 0)
    except Exception as e:
        results['footnotes_error'] = str(e)
        
    # 3. Opinions
    try:
        op_res = service.ingest_opinions(filename, collection='TC_new_format_opinion')
        results['opinions'] = op_res.get('inserted', 0)
    except Exception as e:
        results['opinions_error'] = str(e)
        
    return filename, results

def run_phase_1():
    print("==================================================")
    print("PHASE 1: API Ingestion (PDF -> MongoDB)")
    print("==================================================")
    
    service = IngestService()
    
    pdf_files = sorted([f for f in os.listdir(settings.data_dir) if f.lower().endswith('.pdf')])
    if not pdf_files:
        print(f"No PDF files found in '{settings.data_dir}'. Skipping Phase 1.")
        return

    print(f"-> Found {len(pdf_files)} PDF files to process.\n")

    total_meta, total_fn, total_op = 0, 0, 0
    errors = []

    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i:03d}/{len(pdf_files):03d}] {pdf_file} ", end="", flush=True)
        _, results = process_pdf(pdf_file, service)
        
        meta = results.get('metadata', 0)
        fn = results.get('footnotes', 0)
        op = results.get('opinions', 0)
        
        total_meta += meta
        total_fn += fn
        total_op += op
        
        err_msgs = []
        if 'metadata_error' in results: err_msgs.append(f"Meta: {results['metadata_error']}")
        if 'footnotes_error' in results: err_msgs.append(f"FN: {results['footnotes_error']}")
        if 'opinions_error' in results: err_msgs.append(f"Opinions: {results['opinions_error']}")
            
        if err_msgs:
            print(f"-> ERROR ({', '.join(err_msgs)})")
            errors.append((pdf_file, err_msgs))
        else:
            print(f"-> OK (Meta: {meta}, FN: {fn}, Opinions: {op})")

    print("\n[Phase 1 Summary]")
    print(f"  - Metadata records inserted: {total_meta}")
    print(f"  - Footnote records inserted: {total_fn}")
    print(f"  - Opinion records inserted:  {total_op}")
    
    if errors:
        print(f"  - Encountered {len(errors)} errors during ingestion.")


def run_phase_2():
    print("\n==================================================")
    print("PHASE 2: Data Post-Processing & Enrichment")
    print("==================================================")
    
    scripts = [
        ("1. Metadata Cleanup & Date Conversion", "index_preprocess.py"),
        ("2. Link Classification (Cases, Statutes, etc.)", "link_classify.py"),
        ("3. Case URN Extraction", "buildup_case_urn.py"),
        ("4. Court Circuit Level Annotation", "circuit_level.py"),
        ("5. Judge Background Scraping", "judge.py")
    ]
    
    for step_name, script_name in scripts:
        print(f"\n>>> Running: {step_name} ({script_name})")
        
        if not os.path.exists(script_name):
            print(f"    [Error] Script not found: {script_name}. Skipping!")
            continue
            
        try:
            # We use subprocess to run each script in the same virtual environment
            result = subprocess.run([sys.executable, script_name], check=True, capture_output=True, text=True)
            
            # Print the output of the script with indentation
            for line in result.stdout.splitlines():
                print(f"    {line}")
                
            print("    [Success]")
            
        except subprocess.CalledProcessError as e:
            print(f"    [Failed] Error executing {script_name}")
            print(f"    [Stderr] {e.stderr}")
            # Decide whether to stop the whole pipeline on error, or continue
            print("    Stopping pipeline due to error in post-processing step.")
            break

if __name__ == "__main__":
    run_phase_1()
    run_phase_2()
    print("\n==================================================")
    print("All Pipeline Execution Finished!")
    print("==================================================")
