import sys
import os
from pathlib import Path

# Add 'src' directory to path
src_path = str(Path(os.getcwd()) / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

from preprocess.core.factory import ProcessorFactory

def test_tc():
    file_path = "2025_6 TC.pdf"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found")
        return

    print(f"Processing {file_path}...")
    processor = ProcessorFactory.create_processor(file_path, "tc")
    processor.process()
    
    # Print the cleaned text
    print("\n--- CLEANED TEXT ---")
    print(processor.cleaned_structured_text)
    print("--------------------")
    
    # Print extracted sections
    print("\n--- EXTRACTED SECTIONS ---")
    for key, val in processor.secciones_diccionario.items():
        print(f"[{key}]:\n{val}\n")
    print("--------------------------")

if __name__ == "__main__":
    test_tc()
