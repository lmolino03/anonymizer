from dataclasses import dataclass
from preprocess.core.base_processor import BaseProcessor

@dataclass
class InformeErgoespirometria:
    texto_anonimizado: str
    inicio: str = ""
    capacidad_funcional: str = ""
    respuesta_cardiovascular: str = ""
    respiratoria: str = ""
    ventilacion_perfusion: str = ""
    musculatura_periferica: str = ""
    conclusiones: str = ""
