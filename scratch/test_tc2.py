import re
import sys
import os
sys.path.append(os.path.abspath('src'))
from preprocess.handlers.tc import ProcessorTC

processor = ProcessorTC('2025_6 TC.pdf')
processor.process()

print("EXPLORACIONES:", repr(processor.secciones_diccionario.get('exploraciones')))
print("HALLAZGOS:", repr(processor.secciones_diccionario.get('hallazgos')))
