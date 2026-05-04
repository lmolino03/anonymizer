import unittest
import sys
import os
from pathlib import Path

# Agregar el directorio 'src' al path de búsqueda de módulos para permitir importaciones relativas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from preprocess.core.factory import ProcessorFactory
from preprocess.handlers.alta import ProcessorAlta
from preprocess.handlers.anamnesis import ProcessorAnamnesis
from preprocess.handlers.evolucion import ProcessorEvolucion

class TestProcessorFactory(unittest.TestCase):
    """
    Clase de pruebas unitarias para validar el comportamiento de la factoría de procesadores.
    """

    def test_create_alta_processor(self):
        """
        Verifica que la factoría devuelva una instancia de ProcessorAlta 
        cuando se solicita el tipo de documento 'alta'.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "alta")
        self.assertIsInstance(processor, ProcessorAlta)

    def test_create_anamnesis_processor(self):
        """
        Verifica que la factoría devuelva una instancia de ProcessorAnamnesis 
        cuando se solicita el tipo de documento 'anamnesis'.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "anamnesis")
        self.assertIsInstance(processor, ProcessorAnamnesis)

    def test_create_evolucion_processor(self):
        """
        Verifica que la factoría devuelva una instancia de ProcessorEvolucion 
        cuando se solicita el tipo de documento 'evolucion'.
        """
        processor = ProcessorFactory.create_processor("dummy_path.pdf", "evolucion")
        self.assertIsInstance(processor, ProcessorEvolucion)

    def test_invalid_document_type(self):
        """
        Verifica que el sistema lance una excepción de tipo ValueError
        cuando se solicita un tipo de documento que no está soportado.
        """
        with self.assertRaises(ValueError):
            ProcessorFactory.create_processor("dummy_path.pdf", "tipo_desconocido")

if __name__ == "__main__":
    unittest.main()
