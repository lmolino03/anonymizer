import logging

def clean_structured_text(structured_text, substrings):
    """
    Limpia el structured_text eliminando líneas que contengan cualquiera de los substrings.
    
    Args:
        structured_text (dict): Diccionario con estructura de PDF
        substrings (list): Lista de substrings a filtrar
        
    Returns:
        dict: Structured_text limpio e información sobre líneas eliminadas
    """
    if not structured_text or not substrings:
        return structured_text, 0
    
    # Crear copia de la estructura
    cleaned_structure = {
        "archivo": structured_text["archivo"],
        "total_paginas": structured_text["total_paginas"],
        "metadatos": structured_text["metadatos"],
        "paginas": []
    }
    
    total_lines_removed = 0
    
    # Procesar cada página
    for pagina in structured_text["paginas"]:
        cleaned_page = {
            "pagina": pagina["pagina"],
            "dimensiones": pagina["dimensiones"],
            "lineas": []
        }
        
        # Filtrar líneas que NO contengan ninguno de los substrings
        for linea in pagina["lineas"]:
            texto_completo = linea.get("texto_completo", "")
            
            # Verificar si algún substring está presente (case insensitive)
            contains_substring = any(
                substring.lower() in texto_completo.lower() 
                for substring in substrings
            )
            
            if not contains_substring:
                cleaned_page["lineas"].append(linea)
            else:
                total_lines_removed += 1
        
        cleaned_structure["paginas"].append(cleaned_page)
    
    return cleaned_structure, total_lines_removed
