import fitz  # PyMuPDF
import json
import logging
from collections import defaultdict
import re


from preprocess.readers.pdf_analyzer import PDFLineAnalyzer

import traceback

class PDFReader:
    """Clase para leer archivos PDF con diferentes métodos de extracción."""
    
    @staticmethod
    def read_pdf_text(file_path):
        """
        Lee un archivo PDF y extrae solo el texto plano.
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
        Lee un archivo PDF y extrae información estructurada línea por línea.
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
        Función de utilidad para analizar un PDF y generar reportes en consola y archivos.
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
                print("ESTADÍSTICAS DEL DOCUMENTO")
                print("="*80)
                print(f"Total de páginas: {stats['total_paginas']}")
                print(f"Total de líneas: {stats['total_lineas']}")
                print(f"Total de tablas: {stats['total_tablas']}")
                print(f"Fuentes usadas: {', '.join(stats['fuentes_usadas'])}")
            
            return analysis
        except Exception as e:
            print(f"Error durante el análisis: {str(e)}")
            traceback.print_exc()
            return None
        finally:
            analyzer.close()

    @staticmethod
    def extract_only_text(pdf_path, include_tables=True):
        """
        Extrae solo el texto del PDF de forma simple pero respetando la estructura detectada.
        """
        analyzer = PDFLineAnalyzer(pdf_path)
        try:
            analysis = analyzer.analyze_full_document()
            texto_completo = []
            for page in analysis["paginas"]:
                texto_completo.append(f"\n--- PÁGINA {page['pagina']} ---\n")
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
        Busca un término en el PDF y retorna las líneas que lo contienen.
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


