import fitz  # PyMuPDF
import json
import logging
from collections import defaultdict
import re


from preprocess.readers.pdf_analyzer import PDFLineAnalyzer

import traceback

class PDFReader:
    """Class to read PDF files using different extraction methods."""
    
    @staticmethod
    def read_pdf_text(file_path):
        """
        Reads a PDF file and extracts only plain text.
        """
        try:
            doc = fitz.open(file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logging.error(f"Error reading PDF {file_path}: {e}")
            raise Exception(f"Error reading PDF: {str(e)}")
    
    @staticmethod
    def read_pdf_structured(file_path):
        """
        Reads a PDF file and extracts structured information line by line.
        """
        analyzer = PDFLineAnalyzer(file_path)
        try:
            analysis = analyzer.analyze_full_document()
            return analysis
        except Exception as e:
            logging.error(f"Error analyzing PDF structure {file_path}: {e}")
            raise Exception(f"Error analyzing PDF structure: {str(e)}")
        finally:
            analyzer.close()

    @staticmethod
    def analyze_and_report(pdf_path, output_json_path=None, output_txt_path=None, export_tables=False):
        """
        Utility function to analyze a PDF and generate console and file reports.
        """
        analyzer = PDFLineAnalyzer(pdf_path)
        try:
            analysis = analyzer.analyze_full_document()
            analyzer.print_summary()
            
            if output_json_path:
                analyzer.save_to_json(output_json_path)
            if output_txt_path:
                analyzer.save_to_txt(output_txt_path)
            if export_tables:
                analyzer.export_tables_to_csv()
            
            stats = analyzer.get_statistics()
            if stats:
                print("\n" + "="*80)
                print("DOCUMENT STATISTICS")
                print("="*80)
                print(f"Total pages: {stats['total_paginas']}")
                print(f"Total lines: {stats['total_lineas']}")
                print(f"Total tables: {stats['total_tablas']}")
                print(f"Fonts used: {', '.join(stats['fuentes_usadas'])}")
            
            return analysis
        except Exception as e:
            print(f"Error during analysis: {str(e)}")
            traceback.print_exc()
            return None
        finally:
            analyzer.close()

    @staticmethod
    def extract_only_text(pdf_path, include_tables=True):
        """
        Extracts only the text from the PDF simply while respecting the detected structure.
        """
        analyzer = PDFLineAnalyzer(pdf_path)
        try:
            analysis = analyzer.analyze_full_document()
            texto_completo = []
            for page in analysis["paginas"]:
                texto_completo.append(f"\n--- PAGE {page['pagina']} ---\n")
                for line in page["lineas"]:
                    if not include_tables and line["ubicacion_tabla"]["ubicacion"] == "dentro_tabla":
                        continue
                    texto_completo.append(line["texto_completo"])
            return "\n".join(texto_completo)
        finally:
            analyzer.close()

    @staticmethod
    def search_in_pdf(pdf_path, search_term, ignore_case=True):
        """
        Searches for a term in the PDF and returns lines containing it.
        """
        analyzer = PDFLineAnalyzer(pdf_path)
        try:
            analysis = analyzer.analyze_full_document()
            results = []
            for page in analysis["paginas"]:
                for line in page["lineas"]:
                    texto = line["texto_completo"]
                    term = search_term
                    if ignore_case:
                        texto = texto.lower()
                        term = term.lower()
                    if term in texto:
                        results.append({
                            "pagina": page["pagina"],
                            "numero_linea": line["numero_linea"],
                            "texto": line["texto_completo"]
                        })
            return results
        finally:
            analyzer.close()
