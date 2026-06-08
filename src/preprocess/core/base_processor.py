from abc import ABC, abstractmethod
import logging
from preprocess.readers.pdf_reader import PDFReader

from typing import final


class BaseProcessor(ABC):
    """Abstract base class for all PDF document processors."""
    
    def __init__(self, file_path):
        """
        Initializes the base processor.
        
        Args:
            file_path (str): Path to the PDF file to process
        """
        self.file_path = file_path
        self.text = None
        self.structured_text = None
        self.cleaned_structured_text = None
        self.args = None
    
    @final
    def process(self):
        """
        Template method that orchestrates the entire processing workflow.
        Defines the execution order: read -> clean -> extract -> validate
        """
        try:
            self._read_pdf()
            self._clean()
            self._extract_sections()
            self._validate_result()
        except Exception as e:
            logging.error(f"Error processing file {self.file_path}: {e}")
            raise
    
    def get_sections(self):
        """
        Returns the processed arguments.
        
        Returns:
            tuple/list: The sections extracted from the document
        """
        return self.args
    
    def _read_pdf(self):
        """Reads the content of the PDF file."""
        try:
            self.text = PDFReader.read_pdf_text(self.file_path)
            self.structured_text = PDFReader.read_pdf_structured(self.file_path)
            if not self.text or not self.text.strip():
                raise ValueError("PDF appears to be empty or could not extract text")
        except Exception as e:
            logging.error(f"Failed to read PDF {self.file_path}: {e}")
            raise
    
    @abstractmethod
    def _clean(self):
        """
        Abstract method to apply specific text cleaning.
        Each specific processor must implement its own cleaning logic.
        """
        pass
    
    @abstractmethod
    def _extract_sections(self):
        """
        Abstract method to split text into specific sections.
        Each specific processor must implement its own splitting logic.
        """
        pass
    
    def _validate_result(self):
        """
        Basic result validation.
        Specific processors can override this for additional validations.
        """
        if self.args is None:
            logging.warning(f"No arguments extracted from {self.file_path}")
        
        # Basic validation: check if it's a tuple or list
        if self.args is not None and not isinstance(self.args, (tuple, list)):
            logging.warning(f"Arguments should be a tuple or list, got {type(self.args)}")

    def get_tables_json_data(self):
        """Extracts tables with precise coordinates using PDFLineAnalyzer."""
        from preprocess.readers.pdf_analyzer import PDFLineAnalyzer
        analyzer = PDFLineAnalyzer(self.file_path)
        tables_data = []
        try:
            analysis = analyzer.analyze_full_document()
            for page in analysis.get("paginas", []):
                for t_idx, table in enumerate(page.get("tablas", [])):
                    formatted_table = {
                        "pagina": page["pagina"],
                        "tabla_id": t_idx + 1,
                        "num_filas": table.get("num_rows", 0),
                        "num_columnas": table.get("num_columns", 0),
                        "bbox": table.get("bbox", [0, 0, 0, 0]),
                        "celdas": []
                    }
                    for row in table.get("cells", []):
                        for cell in row:
                            bbox = cell.get("bbox", [0, 0, 0, 0])
                            formatted_table["celdas"].append({
                                "fila": cell.get("row", 0),
                                "columna": cell.get("column", 0),
                                "texto": cell.get("text", ""),
                                "coordenadas": {
                                    "x0": round(bbox[0], 2),
                                    "y0": round(bbox[1], 2),
                                    "x1": round(bbox[2], 2),
                                    "y1": round(bbox[3], 2),
                                    "ancho": round(bbox[2] - bbox[0], 2),
                                    "alto": round(bbox[3] - bbox[1], 2)
                                }
                            })
                    tables_data.append(formatted_table)
            return tables_data
        except Exception as e:
            logging.error(f"Error extrayendo tablas a JSON en {self.file_path}: {e}")
            return []
        finally:
            analyzer.close()
