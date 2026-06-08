from typing import Union
from models.coronariografia_2025_1 import InformeCoronariografia2025_1
from models.coronariografia_2025_4 import InformeCoronariografia2025_4

# Tipo que representa cualquiera de las dos versiones de coronariografía
InformeCoronariografia = Union[InformeCoronariografia2025_1, InformeCoronariografia2025_4]
