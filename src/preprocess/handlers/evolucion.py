from preprocess.core.base_processor import BaseProcessor
import logging
import json
from pathlib import Path
import sys
from preprocess.readers.pdf_analyzer import PDFLineAnalyzer
from utils.utils import clean_structured_text





class ProcessorEvolucion(BaseProcessor):
    """Procesador específico para documentos de alta hospitalaria."""
    
    def __init__(self, file_path):
        """
        Inicializa el procesador de alta.
        
        Args:
            file_path (str): Ruta al archivo PDF de alta
        """
        super().__init__(file_path)
        
    def _agregar_info_tabla_a_lineas(self):
        """
        Analiza las tablas del PDF y agrega información de ubicación de tabla a cada línea.
        
        Esto se hace ANTES de la limpieza para que cada línea sepa en qué celda está.
        Luego, cuando extraigamos secciones, sabremos automáticamente en qué celda están.
        """
        try:
            logging.info(f"Analizando tablas y agregando info a líneas en {self.file_path}")
            
            # Usar PDFLineAnalyzer para obtener info de tabla
            analyzer = PDFLineAnalyzer(self.file_path)
            analysis = analyzer.analyze_full_document()
            analyzer.close()
            
            if not analysis or "paginas" not in analysis:
                logging.warning("No se pudo analizar las tablas del documento")
                return
            
            # Agregar info de tabla a cada línea usando el índice (mapeo 1:1)
            lines_updated = 0
            for p_idx, pagina in enumerate(self.structured_text.get("paginas", [])):
                if p_idx >= len(analysis.get("paginas", [])):
                    break
                
                page_analysis = analysis["paginas"][p_idx]
                for l_idx, linea in enumerate(pagina.get("lineas", [])):
                    if l_idx < len(page_analysis.get("lineas", [])):
                        linea["ubicacion_tabla"] = page_analysis["lineas"][l_idx].get("ubicacion_tabla", {})
                        lines_updated += 1
            
            logging.info(f"Información de tabla agregada a {lines_updated} líneas")
            
        except Exception as e:
            logging.error(f"Error al agregar info de tabla a líneas: {e}")
            import traceback
            logging.error(traceback.format_exc())
        
    def _clean(self):
        """
        Implementa la limpieza específica para documentos de alta.
        1. Busca "procedencia" y elimina todo lo que esté arriba
        2. Encuentra el x_inicio más común y elimina líneas que estén fuera del rango (más o menos)
        3. Para líneas con múltiples spans, mantiene solo el span más cercano a la derecha
        4. NUEVO: Agrega información de tabla a cada línea usando PDFLineAnalyzer
        """

        if not self.structured_text:
            logging.error(f"No structured text available for {self.file_path}")
            return
        
        # NUEVO: Analizar tablas ANTES de limpiar para agregar info a cada línea
        self._agregar_info_tabla_a_lineas()
        
        try:
            # Crear una copia del structured_text para modificar
            cleaned_structured_text = {
                "archivo": self.structured_text["archivo"],
                "total_paginas": self.structured_text["total_paginas"],
                "metadatos": self.structured_text["metadatos"],
                "paginas": []
            }
            
            # Copiar páginas inicialmente
            for pagina in self.structured_text["paginas"]:
                cleaned_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": pagina["lineas"].copy()  # Copia inicial de todas las líneas
                }
                cleaned_structured_text["paginas"].append(cleaned_page)
            
            # Actualizar el structured_text con la copia inicial
            self.structured_text = cleaned_structured_text
            
            # ========== NUEVA FUNCIONALIDAD: Filtro por PROCEDENCIA ==========
            
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
            
            # Buscar "procedencia" en todas las líneas
            procedencia_idx = None
            for i, line_info in enumerate(all_lines_with_position):
                if "procedencia" in line_info["texto"]:
                    procedencia_idx = i
                    logging.info(f"Encontrada línea con 'procedencia' en posición global {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                    break
            
            if procedencia_idx is None:
                error_msg = f"No se encontró la palabra 'procedencia' en el documento {self.file_path}"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
            # Eliminar todo por encima de procedencia
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
                    if global_line_counter >= procedencia_idx:
                        # Mantener esta línea
                        filtered_page["lineas"].append(linea)
                    else:
                        # Eliminar esta línea
                        lines_removed_by_cut += 1
                        logging.debug(f"Eliminando línea por corte procedencia: '{linea.get('texto_completo', '')[:50]}...'")
                    
                    global_line_counter += 1
                
                # Solo añadir páginas que tengan líneas restantes
                if filtered_page["lineas"]:
                    filtered_page["total_lineas_restantes"] = len(filtered_page["lineas"])
                    filtered_pages.append(filtered_page)
            
            # Actualizar la estructura
            self.structured_text["paginas"] = filtered_pages
            logging.info(f"Eliminadas {lines_removed_by_cut} líneas por corte procedencia")
            
            # ========== FIN BÚSQUEDA PROCEDENCIA ==========
            
            # ========== MANEJO DE SPANS: Mantener el span más cercano a la derecha ==========
            
            lines_processed_spans = 0
            
            for pagina in self.structured_text["paginas"]:
                for linea in pagina["lineas"]:
                    spans_detallados = linea.get("spans_detallados", [])
                    
                    if len(spans_detallados) > 1:
                        # Encontrar el span con mayor x_inicio (más a la derecha)
                        span_mas_derecha = None
                        max_x_inicio = float('-inf')
                        
                        for span in spans_detallados:
                            x_inicio_span = span.get("posicion", {}).get("x0", 0)
                            if x_inicio_span > max_x_inicio:
                                max_x_inicio = x_inicio_span
                                span_mas_derecha = span
                        
                        if span_mas_derecha:
                            # Reemplazar spans_detallados con solo el span más a la derecha
                            linea["spans_detallados"] = [span_mas_derecha]
                            # Actualizar el texto_completo con el texto del span seleccionado
                            linea["texto_completo"] = span_mas_derecha.get("texto", "")
                            # IMPORTANTE: Actualizar la posición de la línea mapeando desde el span
                            span_posicion = span_mas_derecha.get("posicion", {})
                            if span_posicion:
                                linea["posicion"].update({
                                    "x_inicio": span_posicion.get("x0", linea["posicion"].get("x_inicio", 0)),
                                    "x_final": span_posicion.get("x1", linea["posicion"].get("x_final", 0)),
                                    "y_superior": span_posicion.get("y0", linea["posicion"].get("y_superior", 0)),
                                    "y_inferior": span_posicion.get("y1", linea["posicion"].get("y_inferior", 0))
                                })
                            # NUEVO: Actualizar también el estilo de la línea con el estilo del span seleccionado
                            span_estilo = span_mas_derecha.get("estilos", {})
                            if span_estilo:
                                linea["formato_principal"]["estilos"] = span_estilo.copy()

                            
                            lines_processed_spans += 1
                            logging.debug(f"Línea con múltiples spans procesada, mantenido span más derecha: '{linea['texto_completo'][:50]}...'")
            
            logging.info(f"Procesadas {lines_processed_spans} líneas con múltiples spans, mantenido el span más a la derecha")
                        
            # ========== FIN MANEJO DE SPANS ==========
            
            # ========== NUEVA FUNCIONALIDAD: Filtro por x_inicio_comun (MAS Y MENOS) ==========
            
            # Recopilar todos los valores de x_inicio de las líneas restantes
            all_x_inicio_values = []
            tolerance = 8.0  # Tolerancia para agrupar x_inicio similares
            
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
                
                # Segunda limpieza: Eliminar líneas cuyo x_inicio esté FUERA del rango (más Y menos)
                lines_removed_count = 0
                
                for pagina in self.structured_text["paginas"]:
                    filtered_lines = []
                    
                    for linea in pagina["lineas"]:
                        x_inicio = linea.get("posicion", {}).get("x_inicio", 0)
                        
                        # Mantener líneas cuyo x_inicio esté dentro del rango común (con tolerancia)
                        if abs(x_inicio - x_inicio_comun) <= tolerance:
                            filtered_lines.append(linea)
                        else:
                            lines_removed_count += 1
                            logging.debug(f"Eliminando línea por x_inicio fuera de rango: '{linea.get('texto_completo', '')[:50]}...' (x_inicio: {x_inicio:.2f}, diferencia: {abs(x_inicio - x_inicio_comun):.2f})")
                    
                    # Actualizar las líneas de la página
                    pagina["lineas"] = filtered_lines
                    pagina["total_lineas_restantes"] = len(filtered_lines)
                
                logging.info(f"Eliminadas {lines_removed_count} líneas por x_inicio fuera del rango común (±{tolerance} de {x_inicio_comun:.2f})")
            
            # ========== FIN NUEVA FUNCIONALIDAD x_inicio ==========
            
            # Opcional: También limpiar el texto plano eliminando líneas correspondientes
            if self.text:
                # Reconstruir el texto plano con las líneas que quedaron
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
        substrings_to_remove = ["Pág", "Page", "Pag", "http", "fdo", "Fdo", "Jaén, a"]
        self.cleaned_structured_text, lines_removed = clean_structured_text(self.structured_text, substrings_to_remove)

    def _analyze_tables(self):
        """
        Analiza las tablas en el PDF usando PDFLineAnalyzer.
        Almacena la información de tablas para su posterior uso.
        """
        try:
            logging.info(f"Analizando tablas en {self.file_path}")
            analyzer = PDFLineAnalyzer(self.file_path)
            analysis = analyzer.analyze_full_document()
            analyzer.close()
            
            # Almacenar análisis completo
            self.table_analysis = analysis
            
            # Extraer información de tablas
            self.tables_info = []
            for page in analysis.get("paginas", []):
                for table in page.get("tablas", []):
                    self.tables_info.append({
                        "pagina": page["pagina"],
                        "tabla": table
                    })
            
            logging.info(f"Encontradas {len(self.tables_info)} tabla(s) en {self.file_path}")
            return self.table_analysis
            
        except Exception as e:
            logging.error(f"Error al analizar tablas en {self.file_path}: {e}")
            self.table_analysis = None
            self.tables_info = []
            return None
    
    def _map_sections_to_table_cells(self):
        """
        Mapea CADA SECCIÓN a su celda usando la información de tabla que YA tienen las líneas.
        
        NUEVO ENFOQUE ROBUSTO:
        - No compara textos
        - Usa la información de ubicación_tabla que ya está en cada línea
        - Para cada sección, mira sus líneas y determina en qué celda están
        - Asigna la sección a la celda donde está la MAYORÍA de sus líneas
        - Detecta secciones multipágina y guarda fusiones de celdas
        """
        if not hasattr(self, 'sections') or not self.sections:
            logging.warning("No hay secciones disponibles para mapeo")
            return
        
        # Rastrear qué tipos de sección ya están en cada celda
        tipos_por_celda = {}  # celda_key -> set(tipos)
        
        # Guardar fusiones de celdas: cuando una sección está en múltiples páginas,
        # las celdas de páginas posteriores se fusionan con la de la primera página
        self.celda_fusiones = {}  # celda_secundaria (fila, pag) -> celda_principal (fila, pag)
        
        # Para cada sección, determinar su celda basándose en sus líneas ORIGINALES
        for section in self.sections:
            section_name = section.get("seccion", "")
            section_body = section.get("cuerpo", "").strip()
            
            if not section_body:
                section["celda_info"] = {"en_tabla": False}
                logging.debug(f"Sección '{section_name}' sin contenido")
                continue
            
            # Extraer tipo de sección
            section_type = self._extraer_tipo_seccion(section_name)
            
            # Obtener las REFERENCIAS a líneas originales (que ya tienen ubicacion_tabla)
            line_refs = section.get("line_refs", [])
            
            if not line_refs:
                section["celda_info"] = {"en_tabla": False}
                logging.debug(f"Sección '{section_name}' sin referencias a líneas")
                continue
            
            # Contar en qué celdas están las líneas de esta sección
            celda_counts = {}  # celda_key -> (count, celda_info)
            
            for linea_ref in line_refs:
                # Obtener ubicacion_tabla DIRECTAMENTE de la línea original
                ubicacion_tabla = linea_ref.get("ubicacion_tabla")
                
                if ubicacion_tabla and ubicacion_tabla.get("ubicacion") == "dentro_tabla":
                    # Obtener página: primero de ubicacion_tabla, luego de _pagina_original, o default 1
                    pagina_num = ubicacion_tabla.get("pagina") or linea_ref.get("_pagina_original", 1)
                    
                    celda_key = (
                        ubicacion_tabla.get("tabla_id"),
                        ubicacion_tabla.get("fila"),
                        ubicacion_tabla.get("columna"),
                        pagina_num
                    )
                    
                    if celda_key not in celda_counts:
                        celda_counts[celda_key] = {
                            "count": 0,
                            "celda_info": {
                                "en_tabla": True,
                                "tabla_id": ubicacion_tabla.get("tabla_id"),
                                "fila": ubicacion_tabla.get("fila"),
                                "columna": ubicacion_tabla.get("columna"),
                                "celda_bbox": ubicacion_tabla.get("celda_bbox"),
                                "pagina": pagina_num
                            }
                        }
                    
                    celda_counts[celda_key]["count"] += 1
            
            # Encontrar la celda con más líneas de esta sección
            if celda_counts:
                logging.debug(f"Sección '{section_name}': {len(celda_counts)} celda(s) candidata(s)")
                
                # NOTA: En evolución, permitimos múltiples secciones en la misma celda
                # sin filtrar por tipo, ya que es común que Evolución y Juicio Clínico
                # compartan la misma fila del registro médico.
                celdas_disponibles = celda_counts
                
                if celdas_disponibles:
                    # Ordenar por: 1) Página (ascendente - primera página primero)
                    #              2) Cantidad de líneas (descendente - más líneas primero)
                    sorted_celdas = sorted(celdas_disponibles.items(), 
                                         key=lambda x: (
                                             x[0][3],  # Página (índice 3 en celda_key)
                                             -x[1]["count"]  # Negativo para ordenar descendente
                                         ))
                    
                    best_celda_key, best_data = sorted_celdas[0]
                    celda_info = best_data["celda_info"]
                    line_count = best_data["count"]
                    
                    # Asignar la celda
                    section["celda_info"] = celda_info
                    
                    # Registrar tipo en celda
                    if best_celda_key not in tipos_por_celda:
                        tipos_por_celda[best_celda_key] = set()
                    tipos_por_celda[best_celda_key].add(section_type)
                    
                    tipos_str = ", ".join(tipos_por_celda[best_celda_key])
                    
                    # NUEVO: Detectar si la sección está en múltiples páginas
                    # y guardar las fusiones de celdas
                    paginas_unicas = set(key[3] for key in celdas_disponibles.keys())
                    if len(paginas_unicas) > 1:
                        # Celda principal (la elegida - primera página)
                        celda_principal = (celda_info['fila'], celda_info['pagina'])
                        
                        # Fusionar todas las celdas de otras páginas con la principal
                        for celda_key in celdas_disponibles.keys():
                            if celda_key != best_celda_key:
                                # Celda secundaria (fila, página) → Celda principal (fila, página)
                                celda_secundaria = (celda_key[1], celda_key[3])  # (fila, página)
                                
                                # Solo fusionar si no existe ya una fusión para esta celda secundaria
                                if celda_secundaria not in self.celda_fusiones:
                                    self.celda_fusiones[celda_secundaria] = celda_principal
                                    logging.info(f"   🔗 Fusión de celdas: "
                                               f"Fila {celda_secundaria[0] + 1} Pag {celda_secundaria[1]} "
                                               f"→ Fila {celda_principal[0] + 1} Pag {celda_principal[1]}")
                    
                    multi_page_info = f", Página {celda_info['pagina']}" if len(paginas_unicas) > 1 else ""
                    
                    logging.info(f"✓ Sección '{section_name}' → "
                                       f"Tabla {celda_info['tabla_id']}, "
                                       f"Fila {celda_info['fila'] + 1}, "
                               f"Columna {celda_info['columna'] + 1}{multi_page_info} "
                               f"({line_count}/{len(line_refs)} líneas) "
                               f"[Tipos: {tipos_str}]")
                else:
                    # Todas las celdas ya tienen este tipo
                    section["celda_info"] = {"en_tabla": False}
                    logging.warning(f"⚠️ Sección '{section_name}': todas las {len(celda_counts)} celda(s) encontrada(s) ya tienen tipo '{section_type}'")
                    logging.warning(f"   Celdas que se saltaron: {list(celda_counts.keys())}")
            else:
                # No se encontraron líneas en tabla
                section["celda_info"] = {"en_tabla": False}
                logging.warning(f"⚠️ Sección '{section_name}' ({len(line_refs)} líneas) no tiene líneas mapeadas a tablas")
                logging.warning(f"   Las líneas están fuera de tablas o no tienen ubicacion_tabla")
        
        # Validación
        self._validar_mapeo_celdas()
    
    def _encontrar_ubicacion_linea(self, texto_linea):
        """
        Busca una línea de texto en cleaned_structured_text y retorna su ubicacion_tabla.
        
        Usa búsqueda exacta primero, luego búsqueda parcial si es necesaria.
        
        Args:
            texto_linea (str): Texto de la línea a buscar
            
        Returns:
            dict: Información de ubicacion_tabla, o None si no se encuentra
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text:
            return None
        
        texto_buscar = texto_linea.strip().lower()
        
        if not texto_buscar or len(texto_buscar) < 2:
            return None
        
        # PASO 1: Búsqueda exacta
        for pagina in self.cleaned_structured_text.get("paginas", []):
            for linea in pagina.get("lineas", []):
                texto_linea_actual = linea.get("texto_completo", "").strip().lower()
                
                if texto_buscar == texto_linea_actual:
                    # Encontrada! Retornar su ubicacion_tabla
                    ubicacion = linea.get("ubicacion_tabla")
                    if ubicacion:
                        # Agregar la página si no está
                        if "pagina" not in ubicacion:
                            ubicacion["pagina"] = pagina["pagina"]
                        return ubicacion
        
        # PASO 2: Búsqueda parcial (una línea contiene a la otra)
        # Solo para líneas suficientemente largas (>10 caracteres)
        if len(texto_buscar) > 10:
            for pagina in self.cleaned_structured_text.get("paginas", []):
                for linea in pagina.get("lineas", []):
                    texto_linea_actual = linea.get("texto_completo", "").strip().lower()
                    
                    # Si una contiene a la otra con más del 90% de similitud
                    if texto_buscar in texto_linea_actual or texto_linea_actual in texto_buscar:
                        if len(texto_linea_actual) > 0:
                            ratio = min(len(texto_buscar), len(texto_linea_actual)) / max(len(texto_buscar), len(texto_linea_actual))
                            if ratio >= 0.9:  # 90% de similitud
                                ubicacion = linea.get("ubicacion_tabla")
                                if ubicacion:
                                    if "pagina" not in ubicacion:
                                        ubicacion["pagina"] = pagina["pagina"]
                                    return ubicacion
        
        return None
    
    def _extraer_tipo_seccion(self, section_name):
        """
        Extrae el tipo de sección eliminando el número al final.
        
        Ejemplos:
            "Juicio_Clinico_1" -> "Juicio_Clinico"
            "Exploracion_2" -> "Exploracion"
            "Pruebas_Complementarias_3" -> "Pruebas_Complementarias"
            "Procedencia_1" -> "Procedencia"
        
        Args:
            section_name (str): Nombre completo de la sección con número
            
        Returns:
            str: Tipo de sección sin el número
        """
        if not section_name:
            return ""
        
        # Separar por el último guión bajo
        parts = section_name.rsplit('_', 1)
        
        if len(parts) == 2:
            # Verificar si la última parte es un número
            try:
                int(parts[1])
                # Es un número, retornar solo la primera parte
                return parts[0]
            except ValueError:
                # No es un número, retornar el nombre completo
                return section_name
        
        # No tiene guión bajo o solo tiene uno, retornar completo
        return section_name
    
    def _normalizar_texto(self, texto):
        """
        Normaliza un texto eliminando saltos de línea, espacios múltiples y caracteres especiales.
        
        Args:
            texto (str): Texto a normalizar
            
        Returns:
            str: Texto normalizado
        """
        import re
        
        if not texto:
            return ""
        
        # Convertir a minúsculas
        texto = texto.lower()
        
        # Eliminar saltos de línea y tabulaciones
        texto = texto.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Eliminar múltiples espacios en blanco
        texto = re.sub(r'\s+', ' ', texto)
        
        # Eliminar espacios al inicio y final
        texto = texto.strip()
        
        return texto
    
    def _calcular_similitud_textos(self, texto1, texto2):
        """
        Calcula la similitud entre dos textos normalizados de forma ESTRICTA y BIDIRECCIONAL.
        
        El algoritmo considera:
        1. Similitud exacta de caracteres (usando longitudes)
        2. Similitud de palabras en AMBAS direcciones
        3. Penalización si hay palabras extra en cualquiera de los textos
        
        Esto evita que "Endocrino" se confunda con "Endocrino con cardiólogo"
        
        Args:
            texto1 (str): Primer texto (normalizado) - texto de la sección
            texto2 (str): Segundo texto (normalizado) - texto de la celda
            
        Returns:
            float: Similitud entre 0.0 y 1.0
        """
        if not texto1 or not texto2:
            return 0.0
        
        # Caso 1: Coincidencia exacta
        if texto1 == texto2:
            return 1.0
        
        # Caso 2: Similitud de caracteres bidireccional
        # Solo si un texto está contenido en el otro Y la diferencia es pequeña
        if texto1 in texto2:
            ratio_caracteres = len(texto1) / len(texto2)
            # Solo considerar alta similitud si el ratio es muy alto (>90%)
            if ratio_caracteres >= 0.9:
                return ratio_caracteres
        
        if texto2 in texto1:
            ratio_caracteres = len(texto2) / len(texto1)
            if ratio_caracteres >= 0.9:
                return ratio_caracteres
        
        # Caso 3: Similitud por palabras - ALGORITMO ESTRICTO BIDIRECCIONAL
        palabras1 = set(texto1.split())
        palabras2 = set(texto2.split())
        
        if not palabras1 or not palabras2:
            return 0.0
        
        # Palabras en común
        palabras_comunes = palabras1.intersection(palabras2)
        
        if not palabras_comunes:
            return 0.0
        
        # Calcular cobertura en AMBAS direcciones
        cobertura_texto1 = len(palabras_comunes) / len(palabras1)  # ¿Cuántas palabras de texto1 están en texto2?
        cobertura_texto2 = len(palabras_comunes) / len(palabras2)  # ¿Cuántas palabras de texto2 están en texto1?
        
        # CLAVE: Usar el PROMEDIO de ambas coberturas (bidireccional)
        # Esto penaliza cuando un texto tiene palabras extra que el otro no tiene
        similitud_bidireccional = (cobertura_texto1 + cobertura_texto2) / 2.0
        
        # También calcular Jaccard como métrica adicional
        palabras_union = palabras1.union(palabras2)
        similitud_jaccard = len(palabras_comunes) / len(palabras_union)
        
        # Retornar el MÍNIMO (más estricto) entre bidireccional y Jaccard
        # Esto asegura que ambos textos sean realmente similares
        return min(similitud_bidireccional, similitud_jaccard)
    
    def _calcular_similitud_linea(self, linea_seccion, linea_tabla):
        """
        Calcula la similitud entre una línea de sección y una línea de tabla.
        Usa múltiples criterios para mejorar la precisión del matching.
        
        Args:
            linea_seccion (str): Línea del cuerpo de la sección
            linea_tabla (str): Línea encontrada en el análisis de tabla
            
        Returns:
            float: Puntuación de similitud (0 = sin similitud, valores más altos = mejor match)
        """
        # Normalizar textos
        linea_sec_lower = linea_seccion.lower().strip()
        linea_tab_lower = linea_tabla.lower().strip()
        
        # Criterio 1: Coincidencia exacta (puntuación máxima)
        if linea_sec_lower == linea_tab_lower:
            return 2.0
        
        # Criterio 2: Una línea contiene a la otra completamente
        # Para líneas suficientemente largas (>15 caracteres)
        if len(linea_sec_lower) > 15 or len(linea_tab_lower) > 15:
            if linea_sec_lower in linea_tab_lower or linea_tab_lower in linea_sec_lower:
                # Puntuación proporcional a la longitud de la línea más corta
                min_len = min(len(linea_sec_lower), len(linea_tab_lower))
                if min_len > 30:
                    return 1.5  # Líneas largas tienen más peso
                elif min_len > 15:
                    return 1.2
            else:
                    return 0.8
        
        # Criterio 3: Coincidencia de palabras significativas
        # Extraer palabras (ignorar palabras muy cortas)
        palabras_seccion = set(p for p in linea_sec_lower.split() if len(p) > 3)
        palabras_tabla = set(p for p in linea_tab_lower.split() if len(p) > 3)
        
        if palabras_seccion and palabras_tabla:
            # Calcular intersección
            palabras_comunes = palabras_seccion.intersection(palabras_tabla)
            
            if palabras_comunes:
                # Calcular ratio de similitud
                ratio = len(palabras_comunes) / min(len(palabras_seccion), len(palabras_tabla))
                
                # Si más del 70% de palabras coinciden
                if ratio >= 0.7:
                    return 1.0
                # Si más del 50% coinciden
                elif ratio >= 0.5:
                    return 0.6
                # Si al menos 3 palabras coinciden
                elif len(palabras_comunes) >= 3:
                    return 0.4
        
        # Criterio 4: Similitud parcial para líneas cortas
        if len(linea_sec_lower) <= 15 and len(linea_tab_lower) <= 15:
            # Para líneas cortas, requiere coincidencia exacta
            if linea_sec_lower == linea_tab_lower:
                return 2.0
            # O que una contenga a la otra con alta similitud
            elif linea_sec_lower in linea_tab_lower or linea_tab_lower in linea_sec_lower:
                longer = max(len(linea_sec_lower), len(linea_tab_lower))
                shorter = min(len(linea_sec_lower), len(linea_tab_lower))
                if shorter / longer > 0.8:  # Al menos 80% de similitud
                    return 0.5
        
        # Sin similitud significativa
        return 0.0
    
    def _validar_mapeo_celdas(self):
        """
        Valida el mapeo de secciones a celdas y reporta posibles problemas.
        
        IMPORTANTE: Una celda PUEDE tener múltiples secciones de DIFERENTES tipos.
        Por ejemplo: Exploracion_1 y Juicio_Clinico_1 pueden estar en la misma celda.
        
        Lo que NO debe pasar es que múltiples secciones del MISMO tipo estén en una celda.
        Por ejemplo: Juicio_Clinico_1 y Juicio_Clinico_2 NO deben compartir celda.
        """
        if not hasattr(self, 'sections') or not self.sections:
            return
        
        # Agrupar secciones por celda
        celda_to_sections = {}
        
        for section in self.sections:
            celda_info = section.get('celda_info', {})
            
            if celda_info.get('en_tabla', False):
                # Crear clave única de celda
                celda_key = (
                    celda_info.get('tabla_id'),
                    celda_info.get('fila'),
                    celda_info.get('columna'),
                    celda_info.get('pagina')
                )
                
                if celda_key not in celda_to_sections:
                    celda_to_sections[celda_key] = []
                
                celda_to_sections[celda_key].append(section.get('seccion', ''))
        
        # Detectar celdas con múltiples secciones del MISMO tipo
        problemas_detectados = False
        for celda_key, secciones in celda_to_sections.items():
            if len(secciones) > 1:
                # Extraer tipos de sección (sin el número)
                tipos_seccion = {}  # tipo -> [secciones con ese tipo]
                
                for sec_name in secciones:
                    tipo = self._extraer_tipo_seccion(sec_name)
                    if tipo not in tipos_seccion:
                        tipos_seccion[tipo] = []
                    tipos_seccion[tipo].append(sec_name)
                
                # Verificar si algún tipo tiene múltiples instancias
                tipos_duplicados = {tipo: secs for tipo, secs in tipos_seccion.items() if len(secs) > 1}
                
                if tipos_duplicados:
                    # ERROR: Múltiples secciones del MISMO tipo en una celda
                    problemas_detectados = True
                    tabla_id, fila, columna, pagina = celda_key
                    logging.warning(
                        f"❌ ERROR: Múltiples secciones del MISMO tipo en una celda:\n"
                        f"  Celda: Tabla {tabla_id}, Fila {fila + 1}, Columna {columna + 1}, Página {pagina}\n"
                    )
                    for tipo, secs in tipos_duplicados.items():
                        logging.warning(f"    Tipo '{tipo}': {', '.join(secs)}")
                elif len(tipos_seccion) > 1:
                    # OK: Múltiples secciones de DIFERENTES tipos (esto es válido)
                    tabla_id, fila, columna, pagina = celda_key
                    tipos_str = ', '.join(tipos_seccion.keys())
                    logging.info(
                        f"✓ Celda compartida correctamente: "
                        f"Tabla {tabla_id}, Fila {fila + 1}, Columna {columna + 1} "
                        f"contiene tipos: {tipos_str}"
                    )
        
        if problemas_detectados:
            logging.warning(
                "⚠️ Se detectaron ERRORES en el mapeo de celdas. "
                "Múltiples secciones del mismo tipo NO deben compartir celda. "
                "Revise las advertencias anteriores."
            )
        else:
            logging.info("✅ Validación de mapeo completada: no se detectaron conflictos")
    
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
        Validación específica para la hoja ed evolucion.
        """
        super()._validate_result()
        
    def _extract_sections(self):
        """
        Extrae secciones en negrita del structured_text para documentos de evolución.
        Cada sección comienza con texto en negrita y continúa hasta la siguiente negrita.
        Si hay secciones con el mismo nombre, se numeran secuencialmente (ej: Exploración_1, Exploración_2).
        
        Returns:
            list: Lista de diccionarios con formato:
                {'seccion': str, 'cuerpo': str, 'numero_seccion': int}
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text or "paginas" not in self.cleaned_structured_text:
            logging.warning(f"No cleaned structured text available for section extraction in {self.file_path}")
            return []
        
        sections = []
        current_section = None
        current_body_lines = []  # Lista de TEXTOS para el cuerpo
        current_body_line_refs = []  # Lista de REFERENCIAS a líneas originales (NUEVO)
        section_counters = {}  # Para llevar el conteo de secciones con el mismo nombre
        
        # Crear una lista global de todas las líneas
        # IMPORTANTE: Agregar número de página a cada línea para distinguirlas
        all_lines = []
        for pagina in self.cleaned_structured_text["paginas"]:
            page_num = pagina["pagina"]
            for linea in pagina["lineas"]:
                # Asegurar que la ubicacion_tabla tenga la página
                if "ubicacion_tabla" in linea:
                    if "pagina" not in linea["ubicacion_tabla"]:
                        linea["ubicacion_tabla"]["pagina"] = page_num
                # También guardar la página directamente en la línea para referencia
                linea["_pagina_original"] = page_num
                all_lines.append(linea)

        def get_bold_info(linea):
            """
            Extrae información sobre texto en negrita de una línea.
            Returns: (is_bold, bold_text)
            """
            texto_completo = linea.get("texto_completo", "").strip()
            spans_detallados = linea.get("spans_detallados", [])
            
            # Verificar el formato principal de la línea
            formato_principal = linea.get("formato_principal", {})
            estilos_principales = formato_principal.get("estilos", [])
            
            if "negrita" in estilos_principales:
                return True, texto_completo
            
            # Si no es negrita en formato principal, verificar spans detallados
            bold_text = ""
            has_bold = False
            
            if spans_detallados:
                for span in spans_detallados:
                    estilos_span = span.get("estilos", [])
                    if "negrita" in estilos_span:
                        has_bold = True
                        bold_text += span.get("texto", "")
                
                if has_bold:
                    return True, bold_text.strip()
            
            # Criterios heurísticos para detectar posibles títulos/secciones
            if not spans_detallados and texto_completo:
                if (len(texto_completo) < 50 and 
                    (texto_completo.isupper() or 
                    texto_completo.endswith(':') or
                    all(word[0].isupper() for word in texto_completo.split() if word))):
                    return True, texto_completo
            
            return False, ""
        
        def normalize_section_name(name):
            """
            Normaliza el nombre de la sección eliminando tildes y sustituyendo espacios por guiones bajos.
            
            Args:
                name (str): Nombre original de la sección
                
            Returns:
                str: Nombre normalizado
            """
            # Diccionario para eliminar tildes
            tildes_map = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
                'ñ': 'n', 'Ñ': 'N'
            }
            
            # Eliminar tildes
            normalized = name
            for tilde, normal in tildes_map.items():
                normalized = normalized.replace(tilde, normal)
            
            # Sustituir espacios por guiones bajos
            normalized = normalized.replace(' ', '_')
            
            return normalized
        
        def save_current_section():
            """Guarda la sección actual en la estructura de datos."""
            nonlocal current_section, current_body_lines, current_body_line_refs, sections
            
            if current_section is not None:
                current_section['cuerpo'] = '\n'.join(current_body_lines).strip()
                current_section['line_refs'] = current_body_line_refs.copy()  # Guardar referencias a líneas originales
                sections.append(current_section)
                current_section = None
                current_body_lines = []
                current_body_line_refs = []
        
        # Procesar todas las líneas
        for i, linea in enumerate(all_lines):
            texto_completo = linea.get("texto_completo", "").strip()
            is_bold, bold_text = get_bold_info(linea)
            
            if is_bold and bold_text.strip():
                # Guardar sección anterior antes de crear nueva
                save_current_section()
                
                # Procesar el nombre de la sección
                section_name = bold_text.strip()
                
                # Limpiar el nombre de la sección (remover ':' al final si existe)
                if section_name.endswith(':'):
                    section_name = section_name[:-1].strip()
                
                # Normalizar el nombre (eliminar tildes y espacios)
                normalized_section_name = normalize_section_name(section_name)
                
                # Contar secciones con el mismo nombre normalizado
                if normalized_section_name in section_counters:
                    section_counters[normalized_section_name] += 1
                else:
                    section_counters[normalized_section_name] = 1
                
                # Crear nombre único con contador
                unique_section_name = f"{normalized_section_name}_{section_counters[normalized_section_name]}"
                
                # Crear nueva sección
                current_section = {
                    'seccion': unique_section_name.strip().rstrip(":").strip(),
                    'cuerpo': '',
                    'numero_seccion': section_counters[normalized_section_name],
                    'nombre_original': section_name
                }
                current_body_lines = []
                current_body_line_refs = []
                
                logging.debug(f"Nueva sección encontrada: '{unique_section_name}' (original: '{section_name}')")
                
            elif texto_completo:
                # Agregar línea al cuerpo de la sección actual
                if current_section is not None:
                    current_body_lines.append(texto_completo)
                    current_body_line_refs.append(linea)  # Guardar referencia a la línea original
        
        # No olvidar la última sección
        save_current_section()
        
        # Guardar las secciones como atributo de la instancia
        self.sections = sections
        logging.info(f"Extracted {len(sections)} sections from {self.file_path}")
        
        # Log resumen de secciones encontradas
        section_summary = {}
        for section in sections:
            original_name = section['nombre_original']
            if original_name in section_summary:
                section_summary[original_name] += 1
            else:
                section_summary[original_name] = 1
        
        logging.info(f"Section summary: {section_summary}")

        # ========== MAPEO A TABLAS ==========
        # Las tablas ya fueron analizadas en _clean() y cada línea tiene ubicacion_tabla
        # Ahora solo mapeamos las secciones a sus celdas
        self._map_sections_to_table_cells()
        # ========== FIN MAPEO ==========

        self.args = sections
        
        return sections

    def print_sections(self):
        """
        Imprime las secciones extraídas en formato legible.
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        if not sections:
            print(f"No se encontraron secciones en negrita en {self.file_path}")
            return
        
        print(f"\n{self.file_path}")
        print(f"Se encontraron {len(sections)} secciones:")
        print("=" * 80)
        
        for i, section in enumerate(sections, 1):
            print(f"\nSECCIÓN {i}: {section['seccion']}")
            print(f"Nombre original: {section['nombre_original']}")
            print(f"Número de repetición: {section['numero_seccion']}")
            print("-" * 60)
            
            if section['cuerpo'].strip():
                print(f"CUERPO:")
                print(section['cuerpo'])
            else:
                print("(Sin contenido)")
            
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
        
        total_sections = len(sections)
        unique_section_names = set(s['nombre_original'] for s in sections)
        
        # Contar repeticiones por nombre
        section_counts = {}
        for section in sections:
            original_name = section['nombre_original']
            if original_name in section_counts:
                section_counts[original_name] += 1
            else:
                section_counts[original_name] = 1
        
        summary = {
            'total_sections': total_sections,
            'unique_section_names': len(unique_section_names),
            'file_path': self.file_path,
            'section_counts': section_counts,
            'sections_with_repetitions': {k: v for k, v in section_counts.items() if v > 1},
            'section_details': []
        }
        
        for section in sections:
            section_detail = {
                'name': section['seccion'],
                'original_name': section['nombre_original'],
                'repetition_number': section['numero_seccion'],
                'has_body': bool(section['cuerpo'].strip()),
                'body_length': len(section['cuerpo'])
            }
            summary['section_details'].append(section_detail)
        
        return summary
    
    def get_structured_text(self, output_dir=None):
        """
        Genera una estructura de carpetas con archivos .txt para cada sección de evolución.
        Las secciones se agrupan por nombre original (ej: todas las "Exploración" juntas).
        
        Args:
            output_dir (str|Path): Directorio base donde crear la estructura.
                                Si es None, se crea junto al archivo fuente.
        
        Returns:
            Path: Ruta del directorio raíz creado
        """
        import re
        from pathlib import Path
        
        try:
            # Asegurarse de que las secciones están extraídas
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determinar directorio de salida
            if output_dir is None:
                source_path = Path(self.file_path)
                output_dir = source_path.parent / f"{source_path.stem}_evolucion_structured"
            else:
                output_dir = Path(output_dir)
            
            # Crear directorio base
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Agrupar secciones por nombre original
            grouped_sections = {}
            for section in self.sections:
                original_name = section['nombre_original']
                if original_name not in grouped_sections:
                    grouped_sections[original_name] = []
                grouped_sections[original_name].append(section)
            
            # Procesar cada grupo de secciones
            for original_name, sections_group in grouped_sections.items():
                # Sanitizar nombre de la sección original
                sanitized_name = self._sanitize_filename(original_name)
                
                if len(sections_group) == 1:
                    # Si solo hay una ocurrencia, crear archivo simple
                    section_file = output_dir / f"{sanitized_name}.txt"
                    section = sections_group[0]
                    
                    with open(section_file, 'w', encoding='utf-8') as f:
                        # Agregar información de celda si está disponible
                        '''celda_info = section.get('celda_info', {})
                        if celda_info.get('en_tabla', False):
                            f.write(f"UBICACIÓN EN TABLA:\n")
                            f.write(f"==================\n")
                            f.write(f"Tabla ID: {celda_info.get('tabla_id')}\n")
                            f.write(f"Fila: {celda_info.get('fila', 0) + 1}\n")
                            f.write(f"Columna: {celda_info.get('columna', 0) + 1}\n")
                            f.write(f"Página: {celda_info.get('pagina')}\n")
                            f.write(f"\n")'''
                        
                        f.write(section['cuerpo'])
                    logging.info(f"Creado archivo: {section_file}")
                else:
                    # Si hay múltiples ocurrencias, crear carpeta
                    section_dir = output_dir / sanitized_name
                    section_dir.mkdir(exist_ok=True)
                    
                    for section in sections_group:
                        section_file = section_dir / f"{section['seccion']}.txt"
                        if section['cuerpo'].strip():
                            with open(section_file, 'w', encoding='utf-8') as f:
                                f.write(section['cuerpo'])
                            logging.info(f"Creado archivo: {section_file}")
            

           
                
            # ========== GENERAR ESTRUCTURA DE CARPETAS POR FILA ==========
            # SIEMPRE generar la agrupación por fila, independientemente de si hay tablas
                self._generar_carpetas_por_celda(output_dir)
            # ========== FIN AGRUPACIÓN POR FILA ==========
            
            logging.info(f"Estructura de texto generada en: {output_dir}")
            return output_dir
        
        except Exception as e:
            logging.error(f"Error al generar estructura de texto para {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def _generar_carpetas_por_celda(self, base_output_dir):
        """
        POST-PROCESAMIENTO: Agrupa las secciones que comparten la misma fila y página.
        IGNORA la columna, solo considera (fila, página).
        
        Por ejemplo, si Exploracion_1 (col 1) y Juicio_Clinico_2 (col 2) están en la 
        misma fila y página, se agruparán en la misma carpeta "fila1_pag1".
        
        Args:
            base_output_dir (Path): Directorio base donde crear las carpetas
        """
        try:
            from collections import defaultdict
            
            base_output_dir = Path(base_output_dir)
            
            # Agrupar secciones por fila y página (IGNORA columna)
            secciones_por_celda = defaultdict(list)
            
            for section in self.sections:
                celda_info = section.get('celda_info', {})
                
                if celda_info.get('en_tabla', False):
                    # Crear clave única solo con fila y página (SIN columna)
                    celda_key = (
                        celda_info.get('fila', 0),
                        celda_info.get('pagina', 1)
                    )
                    
                    secciones_por_celda[celda_key].append(section)
            
            # NUEVO: Aplicar fusiones de celdas
            # Si una celda secundaria debe fusionarse con una principal, mover sus secciones
            if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
                logging.info(f"Aplicando {len(self.celda_fusiones)} fusiones de celdas...")
                
                for celda_secundaria, celda_principal in self.celda_fusiones.items():
                    if celda_secundaria in secciones_por_celda:
                        # Mover todas las secciones de celda secundaria a celda principal
                        secciones_a_mover = secciones_por_celda[celda_secundaria]
                        
                        if secciones_a_mover:
                            logging.info(f"   🔗 Fusionando: "
                                       f"Fila {celda_secundaria[0] + 1} Pag {celda_secundaria[1]} "
                                       f"→ Fila {celda_principal[0] + 1} Pag {celda_principal[1]} "
                                       f"({len(secciones_a_mover)} secciones)")
                            
                            # Agregar a la celda principal
                            secciones_por_celda[celda_principal].extend(secciones_a_mover)
                            
                            # Eliminar la celda secundaria
                            del secciones_por_celda[celda_secundaria]
            
            if not secciones_por_celda:
                logging.info("No hay secciones en tablas para agrupar por celda")
                return
            
            # Crear directorio para carpetas de filas agrupadas
            celdas_dir = base_output_dir / "registros"
            celdas_dir.mkdir(exist_ok=True)
            
            # Crear una carpeta por cada fila que tenga secciones
            # Mantener un mapeo de celda_key a número de registro para el resumen
            # IMPORTANTE: Ordenar primero por página, luego por fila
            celda_to_registro = {}
            registro_counter = 1
            for celda_key, secciones in sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0])):
                fila, pagina = celda_key
                
                # Nombre de la carpeta usando contador secuencial
                carpeta_nombre = f"registro_{registro_counter}"
                celda_to_registro[celda_key] = registro_counter
                celda_dir = celdas_dir / carpeta_nombre
                celda_dir.mkdir(exist_ok=True)
                registro_counter += 1
                
                # Recopilar información de columnas únicas en esta fila
                columnas_en_fila = set()
                tablas_en_fila = set()
                for s in secciones:
                    celda_info = s.get('celda_info', {})
                    if celda_info.get('columna') is not None:
                        columnas_en_fila.add(celda_info.get('columna'))
                    if celda_info.get('tabla_id') is not None:
                        tablas_en_fila.add(celda_info.get('tabla_id'))
                
                # Verificar si esta celda recibió secciones fusionadas
                celdas_fusionadas_aqui = []
                if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
                    for celda_sec, celda_prin in self.celda_fusiones.items():
                        if celda_prin == celda_key:
                            celdas_fusionadas_aqui.append(celda_sec)
                
         

                # Crear archivo consolidado con todas las secciones
                todas_secciones_path = celda_dir / "TODAS_LAS_SECCIONES.txt"
                with open(todas_secciones_path, 'w', encoding='utf-8') as f:
                    f.write(f"TODAS LAS SECCIONES EN ESTA FILA\n")
                    f.write(f"Fila {fila + 1}, Página {pagina}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"Total de secciones: {len(secciones)}\n\n")
                    
                    for section in secciones:
                        celda_info = section.get('celda_info', {})
                        col = celda_info.get('columna', -1)
                        tabla_id = celda_info.get('tabla_id', 0)
                        
                        f.write("\n" + "=" * 60 + "\n")
                        f.write(f"Columna: {col + 1}, Tabla ID: {tabla_id}\n")
                        f.write("=" * 60 + "\n\n")
                        f.write(section.get('cuerpo', ''))
                        f.write("\n\n")
                
                # Crear un archivo individual por cada sección
                for section in secciones:
                    section_name = section.get('seccion', '')
                    sanitized_name = self._sanitize_filename(section_name)
                    section_path = celda_dir / f"{sanitized_name}.txt"
                    
                    celda_info = section.get('celda_info', {})
                    col = celda_info.get('columna', -1)
                    tabla_id = celda_info.get('tabla_id', 0)
                    
                    with open(section_path, 'w', encoding='utf-8') as f:
                        f.write(section.get('cuerpo', ''))
                
                logging.info(f"Carpeta de registro creada: {carpeta_nombre} con {len(secciones)} sección(es)")
            
            # Crear archivo resumen de agrupación
            resumen_path = celdas_dir / "RESUMEN_AGRUPACION.txt"
            with open(resumen_path, 'w', encoding='utf-8') as f:
                f.write("RESUMEN DE AGRUPACIÓN POR FILA Y PÁGINA\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Total de filas con secciones: {len(secciones_por_celda)}\n")
                f.write(f"Total de secciones agrupadas: {sum(len(s) for s in secciones_por_celda.values())}\n\n")
                f.write("NOTA: Las secciones se agrupan por FILA y PÁGINA (ignora columna)\n\n")
                
                # NUEVO: Información sobre fusiones de celdas
                if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
                    f.write("🔗 FUSIONES DE CELDAS APLICADAS:\n")
                    f.write("-" * 70 + "\n")
                    f.write("Cuando una sección se encuentra en múltiples páginas, las secciones\n")
                    f.write("de las páginas posteriores se fusionan con la primera página.\n\n")
                    for celda_sec, celda_prin in sorted(self.celda_fusiones.items()):
                        f.write(f"  • Fila {celda_sec[0] + 1} Pag {celda_sec[1]} "
                              f"→ Fila {celda_prin[0] + 1} Pag {celda_prin[1]}\n")
                    f.write("\n")
                
                f.write("DETALLE DE AGRUPACIÓN:\n")
                f.write("-" * 70 + "\n\n")
                
                # Ordenar primero por página, luego por fila
                for celda_key, secciones in sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0])):
                    fila, pagina = celda_key
                    
                    # Recopilar columnas en esta fila
                    columnas = set()
                    for s in secciones:
                        col = s.get('celda_info', {}).get('columna')
                        if col is not None:
                            columnas.add(col)
                    
                    # Obtener el número de registro para esta celda
                    registro_num = celda_to_registro.get(celda_key, 0)
                    
                    f.write(f"Fila {fila + 1}, Página {pagina}\n")
                    f.write(f"  Carpeta: registro_{registro_num}\n")
                    if columnas:
                        f.write(f"  Columnas presentes: {', '.join(map(lambda x: str(x+1), sorted(columnas)))}\n")
                    f.write(f"  Secciones ({len(secciones)}):\n")
                    for s in secciones:
                        col = s.get('celda_info', {}).get('columna', -1)
                        f.write(f"    - {s.get('seccion', '')} ({s.get('nombre_original', '')}) [Col {col + 1}]\n")
                    f.write("\n")
            
            logging.info(f"Generadas {len(secciones_por_celda)} carpetas de registros en {celdas_dir}")
            
        except Exception as e:
            logging.error(f"Error al generar carpetas por celda: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _sanitize_filename(self, filename):
        """
        Sanitiza un nombre para usarlo como nombre de archivo.
        
        Args:
            filename (str): Nombre original
        
        Returns:
            str: Nombre sanitizado
        """
        import re
        
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
    
    def get_md(self, output_path=None, case_id=None):
        """
        Genera y guarda la hoja de evolución en formato Markdown.
        
        Args:
            output_path (str|Path): Ruta donde guardar el archivo MD. 
                                    Si es None, se guarda en el mismo directorio del archivo fuente
            case_id (str): Identificador del caso (opcional)
        
        Returns:
            Path|None: Ruta del archivo MD generado, o None si hubo error
        """
        from pathlib import Path
        
        try:
            # Asegurarse de que las secciones están extraídas
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determinar la ruta de salida
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_evolucion.md"
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
            
            logging.info(f"Informe MD de evolución generado para {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error al generar archivo MD de evolución para {self.file_path}: {e}")
            return None
    
    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Genera el contenido en formato Markdown desde las secciones extraídas.
        Agrupa secciones por registro (celda/fila) en orden: primero página, luego fila.
        Incluye información de ubicación en tabla cuando está disponible.
        """
        from collections import defaultdict
        
        md_content = "# HOJA DE EVOLUCIÓN\n\n"
        
        if case_id:
            md_content += f"**Número de Caso:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Archivo Fuente:** {file_name}\n\n"
        
        # Agregar información de tablas detectadas
        if hasattr(self, 'tables_info') and self.tables_info:
            md_content += f"**Tablas detectadas:** {len(self.tables_info)}\n\n"
            
            # Contar secciones en tablas
            if hasattr(self, 'sections') and self.sections:
                secciones_en_tabla = sum(1 for s in self.sections if s.get('celda_info', {}).get('en_tabla', False))
                if secciones_en_tabla > 0:
                    md_content += f"**Secciones ubicadas en tablas:** {secciones_en_tabla}\n\n"
        
        md_content += "---\n\n"
        
        # Agrupar secciones por registro (celda/fila)
        secciones_por_celda = defaultdict(list)
        secciones_sin_celda = []
        
        for section in self.sections:
            celda_info = section.get('celda_info', {})
            
            if celda_info.get('en_tabla', False):
                # Crear clave única solo con fila y página (IGNORA columna)
                celda_key = (
                    celda_info.get('fila', 0),
                    celda_info.get('pagina', 1)
                )
                secciones_por_celda[celda_key].append(section)
            else:
                # Secciones fuera de tablas
                secciones_sin_celda.append(section)
        
        # Aplicar fusiones de celdas si existen
        if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
            for celda_secundaria, celda_principal in self.celda_fusiones.items():
                if celda_secundaria in secciones_por_celda:
                    # Mover secciones de celda secundaria a principal
                    secciones_por_celda[celda_principal].extend(secciones_por_celda[celda_secundaria])
                    del secciones_por_celda[celda_secundaria]
        
        # Ordenar registros: primero por página, luego por fila
        registros_ordenados = sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0]))
        
        # Generar contenido por registro
        registro_counter = 1
        for celda_key, secciones in registros_ordenados:
            fila, pagina = celda_key
            
            # Título del registro
            md_content += f"## REGISTRO {registro_counter}\n\n"
            
            
            # Información de columnas presentes
            columnas = set()
            for s in secciones:
                col = s.get('celda_info', {}).get('columna')
                if col is not None:
                    columnas.add(col)
        
            
            md_content += "\n"
            
            # Listar todas las secciones en este registro
            for section in secciones:
                section_name = section.get('nombre_original', section.get('seccion', ''))
                md_content += f"### {section_name}\n\n"
                
                if section['cuerpo'].strip():
                    md_content += f"{section['cuerpo']}\n\n"
            
            md_content += "---\n\n"
            registro_counter += 1
        
        # Agregar secciones sin celda al final si existen
        '''if secciones_sin_celda:
            md_content += "## SECCIONES ADICIONALES\n\n"
            md_content += "> ℹ️ Secciones que no se encuentran dentro de tablas\n\n"
            
            for section in secciones_sin_celda:
                section_name = section.get('nombre_original', section.get('seccion', ''))
                md_content += f"### {section_name}\n\n"
                
                if section['cuerpo'].strip():
                    md_content += f"{section['cuerpo']}\n\n"
            
            md_content += "---\n\n"'''
        
        md_content += "*Informe generado automáticamente*\n"
        
        return md_content
        