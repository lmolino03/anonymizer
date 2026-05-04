from preprocess.core.base_processor import BaseProcessor
import logging
import json
from utils.utils import clean_structured_text

import re
import logging
from pathlib import Path
import pypandoc

class ProcessorAlta(BaseProcessor):
    """Procesador específico para documentos de alta hospitalaria."""
    
    def __init__(self, file_path):
        """
        Inicializa el procesador de alta.
        
        Args:
            file_path (str): Ruta al archivo PDF de alta
        """
        super().__init__(file_path)
    
    def _clean(self):
        """
        Implementa la limpieza específica para documentos de alta.
        Elimina todas las líneas que tienen spans dentro.
        Luego elimina líneas cuyo x_inicio sea mayor al x_inicio más común.
        """

        if not self.structured_text:
            logging.error(f"No structured text available for {self.file_path}")
            return
        
        try:
            # Crear una copia del structured_text para modificar
            cleaned_structured_text = {
                "archivo": self.structured_text["archivo"],
                "total_paginas": self.structured_text["total_paginas"],
                "metadatos": self.structured_text["metadatos"],
                "paginas": []
            }
            
            # Procesar cada página
            for pagina in self.structured_text["paginas"]:
                cleaned_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": []
                }
                
                # Primera limpieza: Filtrar líneas que NO tienen spans (mantener solo las que tienen 0 o 1 spans)
                for linea in pagina["lineas"]:
                    # Verificar si la línea tiene spans detallados
                    '''if not linea.get("spans_detallados") or len(linea.get("spans_detallados", [])) == 1:
                        cleaned_page["lineas"].append(linea)
                    else:
                        print(f"Eliminando línea con spans: '{linea.get('texto_completo', '')[:50]}...'")'''
                    cleaned_page["lineas"].append(linea)

                cleaned_page["total_lineas_restantes"] = len(cleaned_page["lineas"])
                cleaned_structured_text["paginas"].append(cleaned_page)

            
            # Actualizar el structured_text con la primera limpieza
            self.structured_text = cleaned_structured_text
            
            logging.info(f"Cleaned structured text for {self.file_path}. Removed lines with spans.")
            
            # ========== NUEVA FUNCIONALIDAD: Filtro por x_inicio_comun ==========
            
            # Recopilar todos los valores de x_inicio de las líneas limpias
            all_x_inicio_values = []
            tolerance = 22.0  # Tolerancia para agrupar x_inicio similares
            
            for pagina in self.structured_text["paginas"]:
                for linea in pagina["lineas"]:
                    x_inicio = linea.get("posicion", {}).get("x_inicio")
                    if x_inicio is not None:
                        all_x_inicio_values.append(x_inicio)
            
            if not all_x_inicio_values:
                logging.warning(f"No se encontraron valores x_inicio para {self.file_path}")
            else:
                # Agrupar valores similares usando tolerancia
                grouped_x_values = {}
                
                for x_val in all_x_inicio_values:
                    # Buscar si ya existe un grupo similar
                    found_group = None
                    for group_key in grouped_x_values.keys():
                        if abs(x_val - group_key) <= tolerance:
                            found_group = group_key
                            break
                    
                    if found_group is not None:
                        grouped_x_values[found_group].append(x_val)
                    else:
                        grouped_x_values[x_val] = [x_val]
                
                # Encontrar el grupo más común (x_inicio_comun)
                most_common_group = max(grouped_x_values.items(), key=lambda item: len(item[1]))
                x_inicio_comun = most_common_group[0]  # Usar la clave del grupo como referencia
                frequency = len(most_common_group[1])
                
                logging.info(f"x_inicio_comun encontrado: {x_inicio_comun:.2f} (frecuencia: {frequency})")
                
                # Segunda limpieza: Eliminar líneas cuyo x_inicio sea mayor a x_inicio_comun
                lines_removed_count = 0
                
                for pagina in self.structured_text["paginas"]:
                    filtered_lines = []
                    
                    for linea in pagina["lineas"]:
                        x_inicio = linea.get("posicion", {}).get("x_inicio", 0)
                        
                        # Mantener líneas cuyo x_inicio sea menor o igual al común (con tolerancia)
                        if x_inicio <= x_inicio_comun + tolerance:
                            filtered_lines.append(linea)
                        else:
                            lines_removed_count += 1
                            logging.debug(f"Eliminando línea por x_inicio > x_comun: '{linea.get('texto_completo', '')[:50]}...' (x_inicio: {x_inicio:.2f})")
                    
                    # Actualizar las líneas de la página
                    pagina["lineas"] = filtered_lines
                    pagina["total_lineas_restantes"] = len(filtered_lines)
                
                logging.info(f"Eliminadas {lines_removed_count} líneas por x_inicio > x_inicio_comun ({x_inicio_comun:.2f})")
            
            # ========== FIN NUEVA FUNCIONALIDAD ==========
        
            # ========== NUEVO FILTRO: Eliminar líneas que solo contengan "a." ==========
            
            lines_removed_by_a_filter = 0
            
            for pagina in self.structured_text["paginas"]:
                filtered_lines = []
                
                for linea in pagina["lineas"]:
                    n_text = linea.get("texto_completo", "")
                    texto_limpio = n_text.strip().rstrip(":").strip().lower()
                    
                    # Verificar si la línea contiene únicamente "a."
                    if texto_limpio == "a.":
                        lines_removed_by_a_filter += 1
                        logging.debug(f"Eliminando línea que solo contiene 'a.': '{linea.get('texto_completo', '')}'")
                    else:
                        filtered_lines.append(linea)
                
                # Actualizar las líneas de la página
                pagina["lineas"] = filtered_lines
                pagina["total_lineas_restantes"] = len(filtered_lines)
            
            logging.info(f"Eliminadas {lines_removed_by_a_filter} líneas que contenían únicamente 'a.'")
            
            # ========== FIN FILTRO "a." ==========

            
            # ========== BÚSQUEDA Y ELIMINACIÓN POR ANTECEDENTES/MOTIVO ==========
            
            # Crear una lista global de todas las líneas con su posición original
            all_lines_with_position = []
            
            for page_idx, pagina in enumerate(self.structured_text["paginas"]):
                for line_idx, linea in enumerate(pagina["lineas"]):
                    all_lines_with_position.append({
                        "linea": linea,
                        "page_idx": page_idx,
                        "line_idx": line_idx,
                        "global_idx": len(all_lines_with_position),
                        "texto": linea.get("texto_completo", "").lower()
                    })
            
            # Buscar "antecedentes" en todas las líneas
            antecedentes_idx = None
            for i, line_info in enumerate(all_lines_with_position):
                if "antecedentes" in line_info["texto"]:
                    antecedentes_idx = i
                    logging.info(f"Encontrada línea con 'antecedentes' en posición global {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                    break
            
            # Determinar línea de corte
            cut_line_idx = None
            
            if antecedentes_idx is not None:
                print("DEntro antecedntes")
                # Buscar "motivo" por encima de antecedentes (más cercano)
                motivo_idx = None
                for i in range(antecedentes_idx - 1, -1, -1):  # Buscar hacia atrás desde antecedentes
                    if "motivo" in all_lines_with_position[i]["texto"].lower():
                        print("encontrado")
                        motivo_idx = i
                        logging.info(f"Encontrada línea con 'motivo' en posición global {i} (por encima de antecedentes): '{all_lines_with_position[i]['linea'].get('texto_completo', '')[:50]}...'")
                        break
                
                if motivo_idx is not None:
                    # Eliminar todo por encima de motivo
                    cut_line_idx = motivo_idx
                    logging.info(f"Se eliminará todo por encima de la línea con 'motivo' (posición {motivo_idx})")
                else:
                    # No se encontró motivo, eliminar todo por encima de antecedentes
                    cut_line_idx = antecedentes_idx
                    logging.info(f"No se encontró 'motivo' por encima de 'antecedentes'. Se eliminará todo por encima de 'antecedentes' (posición {antecedentes_idx})")
            
            else:
                # No se encontró antecedentes, buscar motivo directamente
                motivo_idx = None
                for i, line_info in enumerate(all_lines_with_position):
                    if "motivo" in line_info["texto"]:
                        motivo_idx = i
                        logging.info(f"No se encontró 'antecedentes'. Encontrada línea con 'motivo' en posición global {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                        break
                
                if motivo_idx is not None:
                    # Eliminar todo por encima de motivo
                    cut_line_idx = motivo_idx
                    logging.info(f"Se eliminará todo por encima de la línea con 'motivo' (posición {motivo_idx})")
                else:
                    # No se encontró ni antecedentes ni motivo - ERROR
                    error_msg = f"No se encontraron las palabras 'antecedentes' ni 'motivo' en el documento {self.file_path}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
            
            # Realizar el corte si se determinó una línea de corte
            if cut_line_idx is not None:
                lines_removed_by_cut = 0
                
                # Crear nueva estructura sin las líneas que están por encima del corte
                filtered_pages = []
                global_line_counter = 0
                
                for page_idx, pagina in enumerate(self.structured_text["paginas"]):
                    filtered_page = {
                        "pagina": pagina["pagina"],
                        "dimensiones": pagina["dimensiones"],
                        "lineas": []
                    }
                    
                    for line_idx, linea in enumerate(pagina["lineas"]):
                        if global_line_counter >= cut_line_idx:
                            # Mantener esta línea
                            filtered_page["lineas"].append(linea)
                        else:
                            # Eliminar esta línea
                            lines_removed_by_cut += 1
                            logging.debug(f"Eliminando línea por corte antecedentes/motivo: '{linea.get('texto_completo', '')[:50]}...'")
                        
                        global_line_counter += 1
                    
                    # Solo añadir páginas que tengan líneas restantes
                    if filtered_page["lineas"]:
                        filtered_page["total_lineas_restantes"] = len(filtered_page["lineas"])
                        filtered_pages.append(filtered_page)
                
                # Actualizar la estructura
                self.structured_text["paginas"] = filtered_pages
                
                logging.info(f"Eliminadas {lines_removed_by_cut} líneas por corte antecedentes/motivo")
            
            # ========== FIN BÚSQUEDA ANTECEDENTES/MOTIVO ==========
            
            # Opcional: También limpiar el texto plano eliminando líneas correspondientes
            if self.text:
                # Reconstruir el texto plano sin las líneas que fueron eliminadas
                clean_text_lines = []
                for pagina in self.structured_text["paginas"]:
                    for linea in pagina["lineas"]:
                        if linea.get("texto_completo"):
                            clean_text_lines.append(linea["texto_completo"])
                
                self.text = "\n".join(clean_text_lines)
            
            logging.info(f"Final cleaning completed for {self.file_path}")
            
        except Exception as e:
            logging.error(f"Error cleaning structured text for {self.file_path}: {e}")
            # En caso de error, mantener el texto original
            pass

        # Limpieza por substrings (código original)
        substrings_to_remove = ["Pág", "Page", "Pag", "http", "fdo", "Fdo", "Jaén", "NHC:"]
        self.cleaned_structured_text, lines_removed = clean_structured_text(self.structured_text, substrings_to_remove)

    
    def _join_from_index(self, text_list, start_index):
        """
        Utility method para unir elementos de una lista desde un índice específico.
        
        Args:
            text_list (list): Lista de strings
            start_index (int): Índice desde donde empezar a unir
            
        Returns:
            str: String unido
        """
        if len(text_list) <= start_index:
            return ""
        
        result = ""
        for i, t in enumerate(text_list):
            if i >= start_index:
                result += t
        
        return result
    

    def _validate_result(self):
        """
        Validación específica para documentos de alta.
        """
        super()._validate_result()

        self.print_bold_sections()
        self.get_sections_summary()


    def _extract_sections(self):
        """
        Extrae secciones en negrita y su contenido posterior del structured_text,
        incluyendo soporte para secciones anidadas (máximo 2 niveles).
        
        Returns:
            list: Lista de diccionarios con formato:
                - Para secciones principales: {'seccion': str, 'cuerpo': str, 'nivel': 1, 'subsecciones': []}
                - Para subsecciones: {'seccion': str, 'cuerpo': str, 'nivel': 2, 'x_posicion': float}
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text or "paginas" not in self.cleaned_structured_text:
            logging.warning(f"No cleaned structured text available for section extraction in {self.file_path}")
            return []
        
        sections = []
        current_main_section = None
        current_subsection = None
        current_body_lines = []
        main_section_x_start = None  # Posición X de la sección principal
        
        # Crear una lista global de todas las líneas
        all_lines = []

        for pagina in self.cleaned_structured_text["paginas"]:
            for linea in pagina["lineas"]:
                all_lines.append(linea)

        
        def get_bold_info(linea):
            """
            Extrae información sobre texto en negrita de una línea.
            Returns: (is_bold, bold_text, x_start_position)
            """
            texto_completo = linea.get("texto_completo", "").strip()
            spans_detallados = linea.get("spans_detallados", [])
            x_start = linea.get("posicion", {}).get("x_inicio", 0)
            
            # Verificar el formato principal de la línea
            formato_principal = linea.get("formato_principal", {})
            estilos_principales = formato_principal.get("estilos", [])
            
            if "negrita" in estilos_principales:
                return True, texto_completo, x_start
            
            # Si no es negrita en formato principal, verificar spans detallados
            bold_text = ""
            min_x_start = float('inf')
            has_bold = False
            
            if spans_detallados:
                for span in spans_detallados:
                    estilos_span = span.get("estilos", [])
                    if "negrita" in estilos_span:
                        has_bold = True
                        bold_text += span.get("texto", "")
                        span_x = span.get("posicion", {}).get("x0", 0)
                        min_x_start = min(min_x_start, span_x)
                
                if has_bold:
                    return True, bold_text.strip(), min_x_start if min_x_start != float('inf') else x_start
            
            # Criterios heurísticos para detectar posibles títulos/secciones
            if not spans_detallados and texto_completo:
                if (len(texto_completo) < 50 and 
                    (texto_completo.isupper() or 
                    texto_completo.endswith(':') or
                    all(word[0].isupper() for word in texto_completo.split() if word))):
                    return True, texto_completo, x_start
            
            return False, "", x_start
        
        def save_current_section():
            """Guarda la sección o subsección actual en la estructura de datos."""
            nonlocal current_main_section, current_subsection, current_body_lines, sections
            
            if current_subsection is not None:
                # Estamos guardando una subsección
                current_subsection['cuerpo'] = '\n'.join(current_body_lines).strip()
                
                # Buscar la sección principal actual y agregar la subsección
                if sections and sections[-1]['nivel'] == 1:
                    sections[-1]['subsecciones'].append(current_subsection)
                else:
                    # Si no hay sección principal, crear una temporal
                    temp_main = {
                        'seccion': f"Sección principal para: {current_subsection['seccion']}",
                        'cuerpo': '',
                        'nivel': 1,
                        'subsecciones': [current_subsection],
                        'x_posicion': current_subsection['x_posicion'] - 10  # Asumir que está más a la izquierda
                    }
                    sections.append(temp_main)
                
                current_subsection = None
                
            elif current_main_section is not None:
                # Estamos guardando una sección principal
                current_main_section['cuerpo'] = '\n'.join(current_body_lines).strip()
                sections.append(current_main_section)
                current_main_section = None
        
        # Procesar todas las líneas
        for i, linea in enumerate(all_lines):
            texto_completo = linea.get("texto_completo", "").strip()
            is_bold, bold_text, x_start = get_bold_info(linea)
            
            if is_bold and bold_text.strip():
                # Determinar si es sección principal o subsección
                is_subsection = False
                
                if main_section_x_start is not None:
                    # Si tenemos una sección principal previa, comparar posiciones X
                    if x_start > main_section_x_start:
                        is_subsection = True
                
                # Guardar sección anterior antes de crear nueva
                save_current_section()
                
                if is_subsection:
                    # Crear nueva subsección
                    current_subsection = {
                        'seccion': bold_text.strip().rstrip(":").strip(),
                        'cuerpo': '',
                        'nivel': 2,
                        'x_posicion': x_start
                    }


                    current_body_lines = []
                else:
                    # Crear nueva sección principal
                    current_main_section = {
                        'seccion': bold_text.strip().rstrip(":").strip(),
                        'cuerpo': '',
                        'nivel': 1,
                        'subsecciones': [],
                        'x_posicion': x_start
                    }
                    main_section_x_start = x_start
                    current_body_lines = []
                    current_subsection = None  # Reset subsección actual


                
            elif texto_completo:
                # Agregar línea al cuerpo de la sección/subsección actual
                if current_subsection is not None or current_main_section is not None:
                    current_body_lines.append(texto_completo)
        
        # No olvidar la última sección
        save_current_section()
        
        # Guardar las secciones como atributo de la instancia
        self.sections = sections
        
        # Convertir secciones al formato compatible con el primer script
        self._convert_sections_to_args()
        
        logging.info(f"Extracted {len(sections)} main sections with nested subsections from {self.file_path}")
        
        return sections

    def _convert_sections_to_args(self):
        """
        Convierte las secciones extraídas al formato del primer script.
        Busca las secciones específicas y las asigna en el orden correcto:
        (motivo, antecedentes, enfermedad, pruebas_complementarias, evolucion, 
         intervencion, juicio, actuacion, tratamiento, revisiones)
        """
        # Inicializar todas las variables como None
        motivo = None
        antecedentes = None
        enfermedad = None
        pruebas_complementarias = None
        evolucion = None
        intervencion = None
        juicio = None
        actuacion = None
        tratamiento = None
        revisiones = None
        
        # Mapeo de nombres de sección a variables (case-insensitive)
        section_mapping = {
            'motivo de consulta': 'motivo',
            'motivo de ingreso': 'motivo',
            'motivo': 'motivo',
            'antecedentes': 'antecedentes',
            'enfermedad actual': 'enfermedad',
            'historia actual': 'enfermedad',
            'pruebas complementarias': 'pruebas_complementarias',
            'resumen pruebas complementarias': 'pruebas_complementarias',
            'evolución y curso clínico': 'evolucion',
            'evolución': 'evolucion',
            'evolucion y comentarios': 'evolucion',
            'intervención quirúrgica / procedimientos': 'intervencion',
            'intervención quirúrgica': 'intervencion',
            'procedimientos': 'intervencion',
            'juicio clínico': 'juicio',
            'juicio clínico - diagnóstico principal': 'juicio',
            'plan de actuación': 'actuacion',
            'plan terapéutico - otras recomendaciones': 'actuacion',
            'tratamiento': 'tratamiento',
            'revisiones': 'revisiones'
        }
        
        # Diccionario para almacenar los contenidos encontrados
        found_sections = {}
        
        # Recorrer todas las secciones extraídas
        for section in self.sections:
            if section['nivel'] == 1:
                section_name = section['seccion'].lower().strip()
                
                # Buscar coincidencia en el mapeo
                for key, var_name in section_mapping.items():
                    if key in section_name:
                        # Combinar el cuerpo de la sección principal con sus subsecciones
                        content = section['cuerpo']
                        
                        # Agregar subsecciones si existen
                        if section.get('subsecciones'):
                            subsection_texts = []
                            for subsec in section['subsecciones']:
                                if subsec['cuerpo'].strip():
                                    subsection_texts.append(f"\n ### {subsec['seccion']}:\n {subsec['cuerpo']}")
                            
                            if subsection_texts:
                                if content.strip():
                                    content += '\n' + '\n'.join(subsection_texts)
                                else:
                                    content = '\n'.join(subsection_texts)
                        
                        found_sections[var_name] = content.strip() if content.strip() else None
                        break
        
        # Asignar los valores encontrados a las variables
        motivo = found_sections.get('motivo')
        antecedentes = found_sections.get('antecedentes')
        enfermedad = found_sections.get('enfermedad')
        pruebas_complementarias = found_sections.get('pruebas_complementarias')
        evolucion = found_sections.get('evolucion')
        intervencion = found_sections.get('intervencion')
        juicio = found_sections.get('juicio')
        actuacion = found_sections.get('actuacion')
        tratamiento = found_sections.get('tratamiento')
        revisiones = found_sections.get('revisiones')
        
        # Crear la tupla en el orden especificado
        self.args = (
            motivo, 
            antecedentes, 
            enfermedad, 
            pruebas_complementarias, 
            evolucion,
            intervencion, 
            juicio, 
            actuacion,
            tratamiento, 
            revisiones
        )
        
        logging.info(f"Converted sections to args format. Found {sum(1 for x in self.args if x is not None)} out of 10 sections")

    def print_bold_sections(self):
        """
        Imprime las secciones extraídas en formato legible, incluyendo subsecciones anidadas.
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        if not sections:
            print(f"No se encontraron secciones en negrita en {self.file_path}")
            return
        
        print(f"\n{self.file_path}")
        print(f"Se encontraron {len(sections)} secciones principales:")
        print("=" * 80)
        
        section_counter = 1
        for section in sections:
            if section['nivel'] == 1:
                print(f"\nSECCIÓN PRINCIPAL {section_counter}: {section['seccion']}")
                print(f"Posición X: {section.get('x_posicion', 'N/A')}")
                print("-" * 60)
                
                if section['cuerpo'].strip():
                    print(f"CUERPO:")
                    print(section['cuerpo'])
                    print()
                
                # Mostrar subsecciones si existen
                if section.get('subsecciones'):
                    print(f"SUBSECCIONES ({len(section['subsecciones'])}):")
                    for i, subsection in enumerate(section['subsecciones'], 1):
                        print(f"  {section_counter}.{i} {subsection['seccion']}")
                        print(f"      Posición X: {subsection.get('x_posicion', 'N/A')}")
                        if subsection['cuerpo'].strip():
                            # Indentar el cuerpo de la subsección
                            subsection_body = '\n'.join(['      ' + line for line in subsection['cuerpo'].split('\n')])
                            print(f"      CUERPO:")
                            print(subsection_body)
                        print()
                
                section_counter += 1
                print("=" * 80)

    def get_sections_summary(self):
        """
        Obtiene un resumen de la estructura de secciones encontradas.
        
        Returns:
            dict: Resumen con estadísticas de las secciones
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        total_main_sections = len([s for s in sections if s['nivel'] == 1])
        total_subsections = sum(len(s.get('subsecciones', [])) for s in sections if s['nivel'] == 1)
        
        summary = {
            'total_main_sections': total_main_sections,
            'total_subsections': total_subsections,
            'sections_with_subsections': len([s for s in sections if s['nivel'] == 1 and s.get('subsecciones')]),
            'file_path': self.file_path,
            'section_details': []
        }
        
        for section in sections:
            if section['nivel'] == 1:
                section_detail = {
                    'name': section['seccion'],
                    'x_position': section.get('x_posicion', 0),
                    'has_body': bool(section['cuerpo'].strip()),
                    'subsections_count': len(section.get('subsecciones', [])),
                    'subsections': [
                        {
                            'name': sub['seccion'],
                            'x_position': sub.get('x_posicion', 0),
                            'has_body': bool(sub['cuerpo'].strip())
                        }
                        for sub in section.get('subsecciones', [])
                    ]
                }
                summary['section_details'].append(section_detail)
        
        return summary
    
    def get_arguments(self):
        """
        Devuelve los argumentos en el formato compatible con el primer script.
        
        Returns:
            tuple: (motivo, antecedentes, enfermedad, pruebas_complementarias, evolucion,
                    intervencion, juicio, actuacion, tratamiento, revisiones)
        """
        if not hasattr(self, 'args'):
            self._extract_sections()
        
        return self.args
    

    def get_md(self, output_path=None, case_id=None):
        """
        Genera y guarda el informe en formato Markdown.
        
        Args:
            output_path (str|Path): Ruta donde guardar el archivo MD. 
                                    Si es None, se guarda en el mismo directorio del archivo fuente
            case_id (str): Identificador del caso (opcional)
        
        Returns:
            Path|None: Ruta del archivo MD generado, o None si hubo error
        """
        try:
            # Asegurarse de que las secciones están extraídas
            if not hasattr(self, 'args'):
                self._extract_sections()
            
            # Determinar la ruta de salida
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_informe.md"
            else:
                output_path = Path(output_path)
            
            # Crear directorio si no existe
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Obtener el nombre del archivo fuente
            file_name = Path(self.file_path).name
            
            # Generar el contenido Markdown
            md_content = self._generate_markdown_content(case_id, file_name)
            
            # Guardar el archivo
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logging.info(f"Informe MD generado para {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error al generar archivo MD para {self.file_path}: {e}")
            return None


    def get_pdf(self, output_path=None, case_id=None):
        """
        Genera y guarda el informe en formato PDF.
        
        Args:
            output_path (str|Path): Ruta donde guardar el PDF. 
                                    Si es None, se guarda en el mismo directorio del archivo fuente
            case_id (str): Identificador del caso (opcional)
        
        Returns:
            Path|None: Ruta del PDF generado, o None si hubo error
        """
        try:
            # Asegurarse de que las secciones están extraídas
            if not hasattr(self, 'args'):
                self._extract_sections()
            
            # Determinar la ruta de salida
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_informe.pdf"
            else:
                output_path = Path(output_path)
            
            # Crear directorio si no existe
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Obtener el nombre del archivo fuente
            file_name = Path(self.file_path).name
            
            # Generar el contenido Markdown
            md_content = self._generate_markdown_content(case_id, file_name)
            
            # Guardar Markdown temporal
            temp_md = output_path.parent / f"{output_path.stem}_temp.md"
            with open(temp_md, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Convertir a PDF usando pypandoc
            pypandoc.convert_file(
                str(temp_md),
                'pdf',
                outputfile=str(output_path),
                extra_args=[
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=2.5cm',
                    '-V', 'fontsize=11pt',
                    '-V', 'mainfont=Arial',  # Usa Arial que está instalada en Windows
                    '--standalone'
                ]
            )
            
            # Eliminar archivo temporal
            temp_md.unlink()
            
            logging.info(f"Informe PDF generado para {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error al generar PDF para {self.file_path}: {e}")
            return None


    def _clean_separator_lines(self, content):
        """
        Elimina líneas que contienen solo guiones (separadores visuales) del contenido.
        
        Args:
            content (str): Contenido Markdown a limpiar
        
        Returns:
            str: Contenido sin líneas de separadores
        """
        if not content:
            return ""
        
        # Dividir en líneas
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Verificar si la línea contiene solo guiones y espacios opcionales
            # Consideramos que 3 o más guiones consecutivos es un separador
            if re.match(r'^\s*-{3,}\s*$', line):
                cleaned_lines.append("\n")
                continue  # Saltar esta línea (no agregarla)
            
            cleaned_lines.append(line)

        
        # Reconstruir el contenido
        return '\n'.join(cleaned_lines)


    def _merge_wrapped_lines(self, content):
        """
        Une líneas que fueron separadas solo por motivos de formato visual.
        Detecta cuando una línea no termina con puntuación fuerte y la une con la siguiente.
        
        Args:
            content (str): Contenido con posibles saltos de línea innecesarios
        
        Returns:
            str: Contenido con líneas unidas apropiadamente
        """
        if not content:
            return ""
        
        # Caracteres que indican fin de oración/párrafo real
        end_punctuation = {'.', '!', '?', ':', ';'}
        
        # Patrones que indican inicio de nueva línea válida
        list_markers = ['-', '•', '*', '·']
        
        lines = content.split('\n')
        merged_lines = []
        current_line = ""
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Si la línea está vacía, es un párrafo nuevo
            if not stripped:
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                merged_lines.append("")
                continue
            
            # Si es inicio de lista o numeración
            is_list_item = any(stripped.startswith(marker) for marker in list_markers)
            is_numbered = len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)-'
            
            if is_list_item or is_numbered:
                if current_line:
                    merged_lines.append(current_line)
                current_line = stripped
                continue
            
            # Si la línea actual tiene contenido
            if current_line:
                # Verificar si la línea anterior termina con puntuación fuerte
                last_char = current_line.rstrip()[-1] if current_line.rstrip() else ''
                
                if last_char in end_punctuation:
                    # Es fin de oración, guardar y empezar nueva línea
                    merged_lines.append(current_line)
                    current_line = stripped
                else:
                    # No termina con puntuación fuerte, unir con espacio
                    current_line += " " + stripped
            else:
                current_line = stripped
        
        # No olvidar la última línea
        if current_line:
            merged_lines.append(current_line)
        
        return '\n'.join(merged_lines)


    # Modificar el método _generate_markdown_content para incluir la limpieza
    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Genera el contenido en formato Markdown desde los argumentos extraídos.
        """
        (motivo, antecedentes, enfermedad, pruebas_complementarias, evolucion,
        intervencion, juicio, actuacion, tratamiento, revisiones) = self.args
        
        md_content = "# INFORME DE ALTA HOSPITALARIA\n\n"
        
        if case_id:
            md_content += f"**Número de Caso:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Archivo Fuente:** {file_name}\n\n"
        
        md_content += "---\n\n"
        
        sections_data = [
            (motivo, "Motivo de Ingreso"),
            (antecedentes, "Antecedentes"),
            (enfermedad, "Historia Actual"),
            (pruebas_complementarias, "Pruebas Complementarias"),
            (evolucion, "Evolución"),
            (intervencion, "Procedimientos e Intervención Quirúrgica"),
            (juicio, "Juicio Clínico y Diagnósticos"),
            (actuacion, "Plan Terapéutico"),
            (tratamiento, "Tratamiento"),
            (revisiones, "Revisiones")
        ]
        
        for content, section_name in sections_data:
            if content and content.strip() and content != 'None':
                # APLICAR LIMPIEZA EN ORDEN:
                # 1. Limpiar separadores de guiones
                cleaned_content = self._clean_separator_lines(content.strip())
                # 2. Unir líneas wrapeadas
                merged_content = self._merge_wrapped_lines(cleaned_content)
                # 3. Formatear saltos de línea
                formatted_content = self._format_markdown_linebreaks(merged_content)
                
                md_content += f"## {section_name}\n\n{formatted_content}\n\n"
        
        md_content += "---\n\n*Informe generado automáticamente*\n"
        
        return md_content


    def _format_markdown_linebreaks(self, content):
        """
        Formatea el contenido para que Markdown preserve los saltos de línea.
        Agrega dos espacios al final de cada línea (sintaxis Markdown) o 
        convierte saltos simples en dobles donde sea apropiado.
        
        Args:
            content (str): Contenido a formatear
        
        Returns:
            str: Contenido formateado para Markdown
        """
        if not content:
            return ""
        
        # Dividir en líneas
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:
                # Si la línea termina con un carácter de puntuación fuerte, agregar línea extra
                if stripped.endswith(('.', ':', '?', '!')):
                    formatted_lines.append(line)
                    formatted_lines.append('')  # Línea vacía para separación
                # Si es una línea de lista (empieza con -, *, número, etc.)
                elif stripped.startswith(('-', '*', '•')) or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)-'):
                    formatted_lines.append(line + '  ')  # Dos espacios al final
                else:
                    formatted_lines.append(line + '  ')  # Dos espacios al final por defecto
            else:
                # Preservar líneas vacías
                formatted_lines.append('')
        
        return '\n'.join(formatted_lines)


    def _clean_markdown_content(self, content, is_first_section=False):
        """
        Limpia el contenido markdown eliminando encabezados redundantes.
        Método auxiliar privado.
        
        Args:
            content (str): Contenido a limpiar
            is_first_section (bool): Si es la primera sección (Motivo de Ingreso)
        
        Returns:
            str: Contenido limpio
        """
        if not content:
            return ""
        
        # Eliminar encabezados de nivel 2 que contengan el nombre de la sección
        content = re.sub(r'^##\s+.*?\n', '', content, flags=re.MULTILINE)
        
        # Dividir en líneas
        lines = content.split('\n')
        
        # Si no es la primera sección, eliminar la primera línea que tenga texto
        if not is_first_section and lines:
            for i, line in enumerate(lines):
                if line.strip():  # Primera línea con contenido
                    lines = lines[i+1:]  # Eliminar desde el inicio hasta esta línea incluida
                    break
        
        # Reconstruir contenido manteniendo saltos de línea
        content = '\n'.join(lines)
        
        return content.strip()
    
    def get_structured_text(self, output_dir=None):
        """
        Genera una estructura de carpetas con archivos .txt para cada sección.
        Trabaja directamente con self.sections para preservar la jerarquía original.
        
        Estructura generada:
        output_dir/
        ├── 01_Motivo_de_ingreso.txt
        ├── 02_Antecedentes/
        │   ├── _principal.txt
        │   ├── Personales.txt
        │   └── Familiares.txt
        ├── 03_Historia_actual.txt
        ├── 04_Pruebas_complementarias.txt
        ├── 05_Evolucion.txt
        ├── 06_Procedimientos_intervencion.txt
        ├── 07_Juicio_clinico_Diagnosticos/
        │   ├── _principal.txt
        │   ├── Diagnostico_principal.txt
        │   └── Secundarios.txt
        ├── 08_Plan_terapeutico.txt
        ├── 09_Tratamiento.txt
        └── 10_Revisiones.txt
        
        Args:
            output_dir (str|Path): Directorio base donde crear la estructura.
                                Si es None, se crea junto al archivo fuente.
        
        Returns:
            Path: Ruta del directorio raíz creado
        """
        try:
            # Asegurarse de que las secciones están extraídas
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determinar directorio de salida
            if output_dir is None:
                source_path = Path(self.file_path)
                output_dir = source_path.parent / f"{source_path.stem}_structured"
            else:
                output_dir = Path(output_dir)
            
            # Crear directorio base
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Contador para numeración de secciones
            section_counter = 1
            
            # Procesar cada sección principal
            for section in self.sections:
                if section['nivel'] != 1:
                    continue
                
                # Sanitizar nombre de sección
                section_name = self._sanitize_filename(section['seccion'])
                
                # Verificar si tiene subsecciones
                has_subsections = section.get('subsecciones') and len(section['subsecciones']) > 0
                
                if has_subsections:
                    # Crear carpeta para sección con subsecciones
                    section_dir = output_dir / f"{section_name}"
                    section_dir.mkdir(exist_ok=True)
                    
                    # Guardar contenido principal si existe
                    if section['cuerpo'].strip():
                        main_content = self._clean_separator_lines(section['cuerpo'])
                        main_content = self._merge_wrapped_lines(main_content)
                        main_file = section_dir / "_principal.txt"
                        
                        with open(main_file, 'w', encoding='utf-8') as f:
                            f.write(main_content)
                        logging.info(f"Creado archivo principal: {main_file}")
                    
                    # Guardar cada subsección
                    for subsection in section['subsecciones']:
                        if subsection['cuerpo'].strip():
                            # Sanitizar nombre de subsección
                            subsec_name = self._sanitize_filename(subsection['seccion'])
                            subsec_content = self._clean_separator_lines(subsection['cuerpo'])
                            subsec_content = self._merge_wrapped_lines(subsec_content)
                            
                            subsec_file = section_dir / f"{subsec_name}.txt"
                            with open(subsec_file, 'w', encoding='utf-8') as f:
                                f.write(subsec_content)
                            logging.info(f"Creada subsección: {subsec_file}")
                    
                    logging.info(f"Creada carpeta con subsecciones: {section_dir}")
                
                else:
                    # Crear archivo único para sección sin subsecciones
                    content = self._clean_separator_lines(section['cuerpo'])
                    content = self._merge_wrapped_lines(content)
                    
                    if content.strip():
                        section_file = output_dir / f"{section_name}.txt"
                        with open(section_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        logging.info(f"Creado archivo: {section_file}")
                
                section_counter += 1
            
            # Crear archivo README con información
            readme_path = output_dir / "README.txt"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"ESTRUCTURA GENERADA DE INFORME DE ALTA\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Archivo fuente: {self.file_path}\n")
                f.write(f"Total de secciones principales: {len([s for s in self.sections if s['nivel'] == 1])}\n")
                f.write(f"Total de subsecciones: {sum(len(s.get('subsecciones', [])) for s in self.sections if s['nivel'] == 1)}\n\n")
                
                f.write("ESTRUCTURA DE CONTENIDO:\n")
                f.write("-" * 60 + "\n\n")
                
                counter = 1
                for section in self.sections:
                    if section['nivel'] == 1:
                        section_name = section['seccion']
                        subsections = section.get('subsecciones', [])
                        
                        if subsections:
                            f.write(f"{counter:02d}. {section_name}/ (carpeta)\n")
                            if section['cuerpo'].strip():
                                f.write(f"    - _principal.txt\n")
                            for subsec in subsections:
                                f.write(f"    - {subsec['seccion']}.txt\n")
                        else:
                            f.write(f"{counter:02d}. {section_name}.txt\n")
                        
                        counter += 1
            
            logging.info(f"Estructura de texto generada en: {output_dir}")
            return output_dir
        
        except Exception as e:
            logging.error(f"Error al generar estructura de texto para {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None


    def _sanitize_filename(self, filename):
        """
        Sanitiza un nombre para usarlo como nombre de archivo.
        
        Args:
            filename (str): Nombre original
        
        Returns:
            str: Nombre sanitizado
        """
        # Eliminar caracteres no permitidos en nombres de archivo
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Reemplazar espacios y guiones por guiones bajos
        sanitized = re.sub(r'[\s\-–—]+', '_', sanitized)
        
        # Eliminar puntos, comas y dos puntos del final
        sanitized = sanitized.strip('.:,;')
        
        # Eliminar caracteres de puntuación adicionales
        sanitized = re.sub(r'[/()]', '', sanitized)
        
        # Limitar longitud del nombre
        if len(sanitized) > 80:
            sanitized = sanitized[:80]
        
        # Capitalizar primera letra de cada palabra
        sanitized = '_'.join(word.capitalize() for word in sanitized.split('_') if word)
        
        return sanitized or "Sin_titulo"
