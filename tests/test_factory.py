import unittest
from pathlib import Path
import sys
import os

# Add the 'src' directory to the Python path so the 'preprocess' module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.preprocess.core.factory import ProcessorFactory
from src.preprocess.handlers.alta import ProcessorAlta
from src.preprocess.handlers.anamnesis import ProcessorAnamnesis
from src.preprocess.handlers.evolucion import ProcessorEvolucion

class TestProcessorFactory(unittest.TestCase):
    """
    Unit test class to validate the behavior of the processor factory.
    """

    def test_create_alta_processor(self):
        """
        Verifies that the factory returns a ProcessorAlta instance 
        when the document type 'alta' is requested.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "alta")
        self.assertIsInstance(processor, ProcessorAlta)

    def test_create_anamnesis_processor(self):
        """
        Verifies that the factory returns a ProcessorAnamnesis instance 
        when the document type 'anamnesis' is requested.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "anamnesis")
        self.assertIsInstance(processor, ProcessorAnamnesis)

    def test_create_evolucion_processor(self):
        """
        Verifies that the factory returns a ProcessorEvolucion instance 
        when the document type 'evolucion' is requested.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "evolucion")
        self.assertIsInstance(processor, ProcessorEvolucion)

    def test_invalid_document_type(self):
        """
        Verifies that the system raises a ValueError exception
        when an unsupported document type is requested.
        """
        with self.assertRaises(ValueError):
            ProcessorFactory.create_processor("dummy_path.pdf", "unknown_type")

if __name__ == "__main__":
    unittest.main()
