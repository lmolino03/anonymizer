from preprocess.handlers.alta import ProcessorAlta
from preprocess.handlers.anamnesis import ProcessorAnamnesis
from preprocess.handlers.evolucion import ProcessorEvolucion
from preprocess.handlers.ergoespirometria import ProcessorErgoespirometria
from preprocess.handlers.laboratorio import ProcessorLaboratorio
from preprocess.handlers.coronariografia import ProcessorCoronariografia
from preprocess.handlers.rmn import ProcessorRMN
from preprocess.handlers.tc import ProcessorTC
from preprocess.handlers.ecocardiograma import ProcessorEcocardiograma
from preprocess.handlers.gammagrafia import ProcessorGammagrafia
class ProcessorFactory:
    """Factory class to create appropriate document processors."""
    
    @staticmethod
    def create_processor(file_path, document_type):
        """
        Creates and returns a processor instance based on document type.
        
        Args:
            file_path (str): Path to the document file
            document_type (str): Type of document ('alta', 'evolucion', 'anamnesis', 'ergoespirometria', 'laboratorio', 'rmn', 'tc', 'gammagrafia')
            
        Returns:
            BaseProcessor: An instance of a specific document processor
            
        Raises:
            ValueError: If the document type is not supported
        """
        processors = {
            'alta': ProcessorAlta,
            'evolucion': ProcessorEvolucion,
            'anamnesis': ProcessorAnamnesis,
            'ergoespirometria': ProcessorErgoespirometria,
            'laboratorio': ProcessorLaboratorio,
            'coronariografia': ProcessorCoronariografia,
            'rmn': ProcessorRMN,
            'tc': ProcessorTC,
            'gammagrafia': ProcessorGammagrafia,
            'ecocardiograma': ProcessorEcocardiograma,
        }
        if document_type not in processors:
            raise ValueError(f"Document type '{document_type}' not supported")
        
        return processors[document_type](file_path)