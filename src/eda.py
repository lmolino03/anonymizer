import sys
import os
import argparse
from pathlib import Path

# Add 'src' directory to path if running from root
src_path = str(Path(__file__).parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from preprocess.readers.pdf_reader import PDFReader

def main():
    """
    Main function for the PDF Exploratory Data Analysis (EDA) tool.
    """
    parser = argparse.ArgumentParser(description="PDF Analysis Tool (EDA)")
    
    # Positional argument: Path to PDF
    parser.add_argument("pdf_path", help="Path to the PDF file to analyze")
    
    # Output options
    parser.add_argument("--json", help="Path to save the analysis in JSON format", default=None)
    parser.add_argument("--txt", help="Path to save the analysis in text format", default=None)
    parser.add_argument("--tables", action="store_true", help="Export found tables to CSV files")
    
    # Specific actions
    parser.add_argument("--extract", action="store_true", help="Perform a simple text extraction")
    parser.add_argument("--search", help="Search for a specific term in the PDF", default=None)
    parser.add_argument("--no-report", action="store_true", help="Do not generate the full console report")

    args = parser.parse_args()

    pdf_path = args.pdf_path
    
    print("="*80)
    print("ADVANCED PDF ANALYZER (ANONIMIZADOR EDA)")
    print("="*80)
    
    if not os.path.exists(pdf_path):
        print(f"\n[!] File {pdf_path} does not exist.")
        sys.exit(1)

    # 1. Full analysis and report (default unless --no-report is used)
    if not args.no_report:
        print("\n" + "="*80)
        print("RUNNING STRUCTURED ANALYSIS")
        print("="*80)
        
        resultado = PDFReader.analyze_and_report(
            pdf_path,
            output_json_path=args.json,
            output_txt_path=args.txt,
            export_tables=args.tables
        )
    
    # 2. Simple extraction if requested
    if args.extract:
        print("\n" + "="*80)
        print("SIMPLE TEXT EXTRACTION")
        print("="*80)
        
        texto = PDFReader.extract_only_text(pdf_path, include_tables=True)
        print(texto[:2000]) # Show the first 2000 characters
        if len(texto) > 2000:
            print("\n... (text truncated in console) ...")
    
    # 3. Search if requested
    if args.search:
        print("\n" + "="*80)
        print(f"SEARCHING FOR TERM: '{args.search}'")
        print("="*80)
        
        resultados = PDFReader.search_in_pdf(pdf_path, args.search)
        print(f"Found {len(resultados)} matches:")
        for res in resultados:
            print(f"  [Page {res['pagina']} Line {res['numero_linea']}]: {res['texto']}")

    print("\n" + "="*80)
    print("PROCESS FINISHED")
    print("="*80)

if __name__ == "__main__":
    main()
