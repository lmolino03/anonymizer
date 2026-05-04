import sys
import os
import argparse
from pathlib import Path

# Añadir el directorio 'src' al path si se ejecuta desde la raíz
src_path = str(Path(__file__).parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from preprocess.readers.pdf_reader import PDFReader

def main():
    parser = argparse.ArgumentParser(description="Herramienta de Análisis de PDFs (EDA)")
    
    # Argumento posicional: Ruta al PDF
    parser.add_argument("pdf_path", help="Ruta al archivo PDF a analizar")
    
    # Opciones de salida
    parser.add_argument("--json", help="Ruta para guardar el análisis en formato JSON", default=None)
    parser.add_argument("--txt", help="Ruta para guardar el análisis en formato texto", default=None)
    parser.add_argument("--tables", action="store_true", help="Exportar tablas encontradas a archivos CSV")
    
    # Acciones específicas
    parser.add_argument("--extract", action="store_true", help="Realizar una extracción simple de texto")
    parser.add_argument("--search", help="Buscar un término específico en el PDF", default=None)
    parser.add_argument("--no-report", action="store_true", help="No generar el reporte completo por consola")

    args = parser.parse_args()

    pdf_path = args.pdf_path
    
    print("="*80)
    print("ANALIZADOR AVANZADO DE PDFs (SIMPLIMED EDA)")
    print("="*80)
    
    if not os.path.exists(pdf_path):
        print(f"\n[!] El archivo {pdf_path} no existe.")
        sys.exit(1)

    # 1. Análisis completo y reporte (por defecto a menos que se use --no-report)
    if not args.no_report:
        print("\n" + "="*80)
        print("EJECUTANDO ANÁLISIS ESTRUCTURADO")
        print("="*80)
        
        resultado = PDFReader.analyze_and_report(
            pdf_path,
            output_json_path=args.json,
            output_txt_path=args.txt,
            export_tables=args.tables
        )
    
    # 2. Extracción simple si se solicita
    if args.extract:
        print("\n" + "="*80)
        print("EXTRACCIÓN SIMPLE DE TEXTO")
        print("="*80)
        
        texto = PDFReader.extract_only_text(pdf_path, include_tables=True)
        print(texto[:2000]) # Mostrar los primeros 2000 caracteres
        if len(texto) > 2000:
            print("\n... (texto truncado en consola) ...")
    
    # 3. Búsqueda si se solicita
    if args.search:
        print("\n" + "="*80)
        print(f"BÚSQUEDA DEL TÉRMINO: '{args.search}'")
        print("="*80)
        
        resultados = PDFReader.search_in_pdf(pdf_path, args.search)
        print(f"Se encontraron {len(resultados)} coincidencias:")
        for res in resultados:
            print(f"  [Pág {res['pagina']} Línea {res['numero_linea']}]: {res['texto']}")

    print("\n" + "="*80)
    print("PROCESO FINALIZADO")
    print("="*80)

if __name__ == "__main__":
    main()
