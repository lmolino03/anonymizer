import pymupdf as fitz  # PyMuPDF
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
    def extract_only_text(pdf_path, include_tables=True, clean_medical_report=True):
        """
        Extracts only the text from the PDF simply while respecting the detected structure.
        Can clean medical report formats by removing template text and empty fields.
        """
        analyzer = PDFLineAnalyzer(pdf_path)
        try:
            analysis = analyzer.analyze_full_document()
            texto_completo = []
            
            in_patient_data_section = False
            stop_extraction = False
            
            for page in analysis["paginas"]:
                if stop_extraction:
                    break
                    
                for line in page["lineas"]:
                    if stop_extraction:
                        break
                        
                    if not include_tables and line["ubicacion_tabla"]["ubicacion"] == "dentro_tabla":
                        continue
                        
                    if not clean_medical_report:
                        texto_completo.append(line["texto_completo"])
                        continue
                        
                    line_text_parts = []
                    last_x1 = None
                    for span in line["spans_detallados"]:
                        texto = span["texto"].strip()
                        if not texto:
                            continue
                            
                        is_bold = "bold" in span["estilos"]
                        is_large = span["tamaño"] > 9.0
                        color = span["color_hex"]
                        
                        if is_bold and is_large:
                            texto_lower = texto.lower()
                            if "paciente" in texto_lower or "peticionario" in texto_lower:
                                in_patient_data_section = True
                                continue
                            elif "datos del informe" in texto_lower or "datos de informe" in texto_lower or "datos clínicos" in texto_lower or "sospecha diagnóstica" in texto_lower:
                                in_patient_data_section = False
                                last_x1 = span.get("posicion", {}).get("x1")
                                line_text_parts.append(texto)
                                continue
                                
                        texto_lower = texto.lower()
                        is_hospital_header = any(h in texto_lower for h in [
                            "complejo hospitalario", 
                            "servicio:", 
                            "unidad:", 
                            "teléfono:"
                        ])
                        
                        if is_hospital_header:
                            continue
                            
                        if in_patient_data_section:
                            continue
                            
                        if last_x1 is not None:
                            distance = span.get("posicion", {}).get("x0", 0) - last_x1
                            if distance > 15:
                                # Calculamos el número de espacios de forma proporcional a la distancia real
                                num_spaces = max(5, int(distance / 3))
                                line_text_parts.append(" " * num_spaces)
                            else:
                                line_text_parts.append(" ")
                                
                        line_text_parts.append(texto)
                        last_x1 = span.get("posicion", {}).get("x1")
                        
                    if line_text_parts:
                        line_text = "".join(line_text_parts)
                        
                        line_text_lower = line_text.lower()
                        if line_text_lower.startswith("estado del informe:"):
                            stop_extraction = True
                            break
                            
                        if re.match(r"^page \d+ of \d+$", line_text_lower):
                            continue
                        if line_text_lower.startswith("código de informe:"):
                            continue
                        if line_text_lower.startswith("http://") or line_text_lower.startswith("https://"):
                            continue
                            
                        texto_completo.append(line_text)
                        
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
