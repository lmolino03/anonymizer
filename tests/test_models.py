import sys
import os
from pathlib import Path

# Configurar PYTHONPATH para encontrar 'src'
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

from preprocess.core.factory import ProcessorFactory
from models.anamnesis import HojaAnamnesis
from models.alta import HojaAlta
from models.evolucion import HojaEvolucion, RegistroEvolucion

def test_anamnesis_model_integration():
    print("\n--- TEST: INTEGRACIÓN ANAMNESIS + MODELO ---")
    pdf_path = project_root / "Anamnesis_10.pdf"
    
    if not pdf_path.exists():
        print(f"Error: No se encuentra {pdf_path}")
        return

    # 1. Extraer datos con el procesador
    processor = ProcessorFactory.create_processor(str(pdf_path), "anamnesis")
    processor.process()
    sections = processor.args 
    # 2. Mapear secciones a los argumentos del modelo
    def get_body(name):
        for s in sections:
            if name.lower() in s['seccion'].lower():
                return s['cuerpo']
        return "No encontrado"

    args = (
        get_body("Motivo"),
        get_body("Antecedentes"),
        get_body("Enfermedad Actual"),
        get_body("Exploración"),
        get_body("Pruebas Complementarias"),
        get_body("Juicio Clínico"),
        get_body("Plan de Actuación")
    )

    # 3. Crear instancia del modelo
    hoja = HojaAnamnesis(args)
    
    # 4. Validar
    print("Modelo instanciado correctamente.")
    print(f"Motivo extraído: {hoja['motivo'][:50]}...")
    print(f"Juicio Clínico: {hoja['juicio'][:50]}...")
    
    print("\nRepresentación __str__ del modelo:")
    print("-" * 30)
    print(str(hoja)[:300] + "...")
    print("-" * 30)

def test_evolucion_model_integration():
    print("\n--- TEST: INTEGRACIÓN EVOLUCIÓN + MODELO ---")
    pdf_path = project_root / "Hoja_evolucion_10.pdf"
    
    if not pdf_path.exists():
        print(f"Error: No se encuentra {pdf_path}")
        return

    processor = ProcessorFactory.create_processor(str(pdf_path), "evolucion")
    processor.process() # Esto genera las carpetas/registros internamente
    
    # Para evolución, el modelo HojaEvolucion agrupa los registros
    hoja_evo = HojaEvolucion()
    
    # Simulamos el llenado del modelo a partir de las secciones procesadas
    # (En una implementación real, esto se haría dentro del procesador o un adaptador)
    from collections import defaultdict
    registros_dict = defaultdict(dict)
    
    for s in processor.sections:
        celda = s.get('celda_info', {})
        if celda.get('en_tabla'):
            key = (celda['fila'], celda['pagina'])
            tipo = s['seccion'].split('_')[0] # ej: 'Evolucion'
            registros_dict[key][tipo] = s['cuerpo']
            
    for (fila, pag), secciones in registros_dict.items():
        registro = RegistroEvolucion(fila + 1, pag, secciones)
        hoja_evo.agregar_registro(registro)

    print(f"Modelo HojaEvolucion creado con {len(hoja_evo)} registros.")
    if len(hoja_evo) > 0:
        primer_reg = hoja_evo.registros[0]
        print(f"Primer {primer_reg}")

if __name__ == "__main__":
    try:
        test_anamnesis_model_integration()
        test_evolucion_model_integration()
        print("\n✅ Todas las pruebas de modelos completadas con éxito.")
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
