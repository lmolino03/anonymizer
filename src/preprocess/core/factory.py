from preprocess.handlers.alta import ProcessorAlta
from preprocess.handlers.anamnesis import ProcessorAnamnesis
from preprocess.handlers.evolucion import ProcessorEvolucion
from preprocess.handlers.tc import ProcessorTC

class ProcessorFactory:
    """Factory class to create appropriate document processors."""
    
    @staticmethod
    def create_processor(file_path, document_type):
        """
        Creates and returns a processor instance based on document type.
        
        Args:
            file_path (str): Path to the document file
            document_type (str): Type of document ('alta', 'evolucion', 'anamnesis')
            
        Returns:
            BaseProcessor: An instance of a specific document processor
            
        Raises:
            ValueError: If the document type is not supported
        """
        processors = {
            'alta': ProcessorAlta,
            'evolucion': ProcessorEvolucion,
            'anamnesis': ProcessorAnamnesis,
            'tc': ProcessorTC
        }
        if document_type not in processors:
            raise ValueError(f"Document type '{document_type}' not supported")
        
        return processors[document_type](file_path)