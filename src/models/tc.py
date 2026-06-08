from dataclasses import dataclass
from preprocess.core.base_processor import BaseProcessor

@dataclass
class InformeTC:
    texto_anonimizado: str
    datos_informe: str = ""
    informe_principal: str = ""
    datos_clinicos: str = ""
    exploraciones: str = ""
    anatomias: str = ""
    hallazgos: str = ""
    indicacion: str = ""
    recomendaciones: str = ""