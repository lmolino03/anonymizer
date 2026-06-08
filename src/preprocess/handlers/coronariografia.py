import logging
from preprocess.readers.pdf_analyzer import PDFLineAnalyzer
from preprocess.handlers.coronariografia_2025_1 import ProcessorCoronariografia2025_1
from preprocess.handlers.coronariografia_2025_4 import ProcessorCoronariografia2025_4

logger = logging.getLogger(__name__)

class ProcessorCoronariografia:
    """
    Router que identifica el tipo de coronariografía (2025_1 o 2025_4) 
    basándose en el contenido de texto del documento, y devuelve el procesador correspondiente.
    """
    def __new__(cls, file_path):
        analyzer = PDFLineAnalyzer(file_path)
        is_format_4 = False
        
        try:
            analysis = analyzer.analyze_full_document()
            
            texto_completo = ""
            if analysis and "paginas" in analysis:
                for page in analysis["paginas"]:
                    for line in page["lineas"]:
                        texto_completo += line.get("texto_completo", "") + " "
            
            texto_lower = texto_completo.lower()
            
            # Palabras clave del formato 4
            keywords_4 = [
                "descripción general del proceso",
                "procedimientos realizados",
                "conclusiones finales y recomendaciones"
            ]
            
            # Si contiene alguna de las palabras clave del formato 4, es 2025_4
            if any(kw in texto_lower for kw in keywords_4):
                is_format_4 = True
                
        except Exception as e:
            logger.error(f"Error analizando el documento en {file_path}: {e}")
        finally:
            analyzer.close()

        if not is_format_4:
            logger.info(f"Detectado formato 2025_1 para coronariografía en {file_path}.")
            return ProcessorCoronariografia2025_1(file_path)
        else:
            logger.info(f"Detectado formato 2025_4 para coronariografía en {file_path}.")
            return ProcessorCoronariografia2025_4(file_path)
