import sys
import os
from pathlib import Path

# Añadir el directorio 'src' al path para las importaciones
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")

if src_path not in sys.path:
    sys.path.append(src_path)

try:
    from preprocess.core.factory import ProcessorFactory
    print("Importaciones desde 'src' exitosas.")
except ImportError as e:
    print(f"Error de importación: {e}")
    sys.exit(1)

def run_test_on_file(file_name, doc_type):
    """
    Ejecuta el procesamiento sobre un archivo específico y muestra resultados.
    """
    # El archivo está en el directorio raíz (un nivel arriba de tests/)
    project_root = Path(__file__).parent.parent
    file_path = str(project_root / file_name)
    
    print(f"\n" + "="*60)
    print(f"PROBANDO: {file_name}")
    print(f"TIPO: {doc_type}")
    print("="*60)
    
    if not os.path.exists(file_path):
        print(f"ERROR: El archivo no se encuentra en {file_path}")
        return False
    
    try:
        # 1. Crear procesador
        print(f"Iniciando procesador para {doc_type}...")
        processor = ProcessorFactory.create_processor(file_path, doc_type)
        
        # 2. Procesar
        print("Ejecutando limpieza y extracción...")
        processor.process()
        
        # 3. Validar resultados básicos
        num_secciones = len(processor.sections)
        print(f"OK: Se han extraído {num_secciones} secciones.")
        
        # 4. Generar Markdown de prueba en la raíz
        output_md = project_root / f"TEST_RESULT_{doc_type}.md"
        processor.get_md(str(output_md))
        print(f"OK: Markdown generado en {output_md.name}")
        
        return True
        
    except Exception as e:
        print(f"ERROR CRÍTICO durante el procesamiento: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("INICIANDO PRUEBA DE INTEGRACIÓN MODULAR")
    
    # Lista de archivos a probar
    tests = [
        ("alta.pdf", "alta"),
        ("Anamnesis_10.pdf", "anamnesis"),
        ("Hoja_evolucion_10.pdf", "evolucion")
    ]
    
    success_count = 0
    for file_name, doc_type in tests:
        if run_test_on_file(file_name, doc_type):
            success_count += 1
    
    print("\n" + "="*60)
    print(f"RESUMEN: {success_count}/{len(tests)} archivos procesados con éxito.")
    print("="*60)
