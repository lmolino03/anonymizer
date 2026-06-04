from dataclasses import dataclass

@dataclass
class InformeRMN:
    texto_anonimizado: str
    datos_informe: str = ""
    informe_principal: str = ""
    datos_clinicos: str = ""
    exploraciones: str = ""
    anatomias: str = ""
    hallazgos: str = ""
    indicacion: str = ""
    recomendaciones: str = ""
