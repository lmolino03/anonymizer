import logging

def clean_structured_text(structured_text, substrings):
    """
    Cleans structured_text by removing lines containing any of the substrings.
    
    Args:
        structured_text (dict): Dictionary with PDF structure
        substrings (list): List of substrings to filter
        
    Returns:
        tuple: (dict: cleaned structured_text, int: count of removed lines)
    """
    if not structured_text or not substrings:
        return structured_text, 0
    
    # Create a copy of the structure
    cleaned_structure = {
        "archivo": structured_text["archivo"],
        "total_paginas": structured_text["total_paginas"],
        "metadatos": structured_text["metadatos"],
        "paginas": []
    }
    
    total_lines_removed = 0
    
    # Process each page
    for pagina in structured_text["paginas"]:
        cleaned_page = {
            "pagina": pagina["pagina"],
            "dimensiones": pagina["dimensiones"],
            "lineas": []
        }
        
        # Filter lines that do NOT contain any of the substrings
        for linea in pagina["lineas"]:
            texto_completo = linea.get("texto_completo", "")
            
            # Check if any substring is present (case insensitive)
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
