import sys
import os
from pathlib import Path

# Add 'src' directory to path for imports
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")

if src_path not in sys.path:
    sys.path.append(src_path)

try:
    from preprocess.core.factory import ProcessorFactory
    print("Imports from 'src' successful.")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def run_test_on_file(file_name, doc_type):
    """
    Runs processing on a specific file and displays results.
    """
    # The file is in the root directory (one level above tests/)
    project_root = Path(__file__).parent.parent
    file_path = str(project_root / file_name)
    
    print(f"\n" + "="*60)
    print(f"TESTING: {file_name}")
    print(f"TYPE: {doc_type}")
    print("="*60)
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return False
    
    try:
        # 1. Create processor
        print(f"Starting processor for {doc_type}...")
        processor = ProcessorFactory.create_processor(file_path, doc_type)
        
        # 2. Process
        print("Running cleaning and extraction...")
        processor.process()
        
        # 3. Validate basic results
        num_secciones = len(processor.sections)
        print(f"OK: {num_secciones} sections extracted.")
        
        # 4. Generate test Markdown in the root
        output_md = project_root / f"TEST_RESULT_{doc_type}.md"
        processor.get_md(str(output_md))
        print(f"OK: Markdown generated at {output_md.name}")
        
        return True
        
    except Exception as e:
        print(f"CRITICAL ERROR during processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("STARTING MODULAR INTEGRATION TEST")
    
    # List of files to test
    tests = [
        ("alta.pdf", "alta"),
        ("Anamnesis_10.pdf", "anamnesis"),
        ("Hoja_evolucion_10.pdf", "evolucion")
    ]
    
    success_count = 0
    for file_name, doc_type in tests:
        if run_test_on_file(file_name, doc_type):
            success_count += 1
    
    print("\n" + "="*60)
    print(f"SUMMARY: {success_count}/{len(tests)} files processed successfully.")
    print("="*60)
