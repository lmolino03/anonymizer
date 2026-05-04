import unittest
import sys
import os
from pathlib import Path

# Add 'src' directory to module search path to allow relative imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from preprocess.core.factory import ProcessorFactory
from preprocess.handlers.alta import ProcessorAlta
from preprocess.handlers.anamnesis import ProcessorAnamnesis
from preprocess.handlers.evolucion import ProcessorEvolucion

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
