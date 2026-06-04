from dataclasses import dataclass

@dataclass
class InformeLaboratorio:
    texto_anonimizado: str
    inicio: str = ""
    hematologia_general: str = ""
    hemostasia_fibrinolisis: str = ""
    bioquimica_general: str = ""
    proteinas_especificas: str = ""
    vitaminas_sangre: str = ""
