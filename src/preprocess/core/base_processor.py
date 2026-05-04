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
