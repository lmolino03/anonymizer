import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from preprocess.readers.pdf_analyzer import PDFLineAnalyzer

pdf_path = r"c:\Users\blas2\Desktop\UJA\Repo\BLAS2_Ejemplo Laboratorio.pdf"
analyzer = PDFLineAnalyzer(pdf_path)
analysis = analyzer.analyze_full_document()

page1 = analysis['paginas'][0]
print(f"--- PAGE 1 ---")
for line in page1['lineas']:
    txt = line['texto_completo']
    styles = line['formato_principal']['estilos']
    is_upper = line['metadatos']['es_mayusculas']
    print(f"Line {line['numero_linea']}: [{txt.strip()}] styles={styles} is_upper={is_upper}")
analyzer.close()
