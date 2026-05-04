import sys
import os
from pathlib import Path

# Configure PYTHONPATH to find 'src'
project_root = Path(__file__).parent.parent
src_path = str(project_root / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

from preprocess.core.factory import ProcessorFactory
from models.anamnesis import HojaAnamnesis
from models.alta import HojaAlta
from models.evolucion import HojaEvolucion, RegistroEvolucion

def test_anamnesis_model_integration():
    """
    Tests the integration between the anamnesis processor and the data model.
    """
    print("\n--- TEST: ANAMNESIS + MODEL INTEGRATION ---")
    pdf_path = project_root / "Anamnesis_10.pdf"
    
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        return

    # 1. Extract data with processor
    processor = ProcessorFactory.create_processor(str(pdf_path), "anamnesis")
    processor.process()
    sections = processor.args 
    
    # 2. Map sections to model arguments
    def get_body(name):
        # This is a simplified mapping for testing purposes
        for s in processor.sections:
            if name.lower() in s['seccion'].lower():
                return s['cuerpo']
        return "Not found"

    args = (
        get_body("Motivo"),
        get_body("Antecedentes"),
        get_body("Enfermedad Actual"),
        get_body("Exploración"),
        get_body("Pruebas Complementarias"),
        get_body("Juicio Clínico"),
        get_body("Plan de Actuación")
    )

    # 3. Create model instance
    hoja = HojaAnamnesis(args)
    
    # 4. Validate
    print("Model instantiated successfully.")
    print(f"Extracted Reason: {hoja['motivo'][:50]}...")
    print(f"Clinical Judgment: {hoja['juicio'][:50]}...")
    
    print("\nModel __str__ representation:")
    print("-" * 30)
    print(str(hoja)[:300] + "...")
    print("-" * 30)

def test_evolucion_model_integration():
    """
    Tests the integration between the evolution processor and the data model.
    """
    print("\n--- TEST: EVOLUTION + MODEL INTEGRATION ---")
    pdf_path = project_root / "Hoja_evolucion_10.pdf"
    
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        return

    processor = ProcessorFactory.create_processor(str(pdf_path), "evolucion")
    processor.process() # This generates folders/records internally
    
    # For evolution, the HojaEvolucion model groups the records
    hoja_evo = HojaEvolucion()
    
    # Simulate filling the model from processed sections
    from collections import defaultdict
    registros_dict = defaultdict(dict)
    
    for s in processor.sections:
        celda = s.get('celda_info', {})
        if celda.get('en_tabla'):
            key = (celda['fila'], celda['pagina'])
            tipo = s['seccion'].split('_')[0] # e.g., 'Evolucion'
            registros_dict[key][tipo] = s['cuerpo']
            
    for (fila, pag), secciones in registros_dict.items():
        registro = RegistroEvolucion(fila + 1, pag, secciones)
        hoja_evo.agregar_registro(registro)

    print(f"HojaEvolucion model created with {len(hoja_evo)} records.")
    if len(hoja_evo) > 0:
        primer_reg = hoja_evo.registros[0]
        print(f"First {primer_reg}")

if __name__ == "__main__":
    try:
        test_anamnesis_model_integration()
        test_evolucion_model_integration()
        print("\n✅ All model tests completed successfully.")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
