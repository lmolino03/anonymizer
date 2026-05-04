from preprocess.core.base_processor import BaseProcessor
import logging
import json
from pathlib import Path
import sys
from preprocess.readers.pdf_analyzer import PDFLineAnalyzer
from utils.utils import clean_structured_text


class ProcessorEvolucion(BaseProcessor):
    """Specific processor for hospital evolution sheet documents."""
    
    def __init__(self, file_path):
        """
        Initializes the evolution processor.
        
        Args:
            file_path (str): Path to the evolution PDF file
        """
        super().__init__(file_path)
        
    def _agregar_info_tabla_a_lineas(self):
        """
        Analyzes PDF tables and adds table location information to each line.
        
        This is done BEFORE cleaning so each line knows which cell it belongs to.
        Later, when extracting sections, we will automatically know their cell location.
        """
        try:
            logging.info(f"Analyzing tables and adding info to lines in {self.file_path}")
            
            # Use PDFLineAnalyzer to get table information
            analyzer = PDFLineAnalyzer(self.file_path)
            analysis = analyzer.analyze_full_document()
            analyzer.close()
            
            if not analysis or "paginas" not in analysis:
                logging.warning("Could not analyze document tables")
                return
            
            # Add table info to each line using index (1:1 mapping)
            lines_updated = 0
            for p_idx, pagina in enumerate(self.structured_text.get("paginas", [])):
                if p_idx >= len(analysis.get("paginas", [])):
                    break
                
                page_analysis = analysis["paginas"][p_idx]
                for l_idx, linea in enumerate(pagina.get("lineas", [])):
                    if l_idx < len(page_analysis.get("lineas", [])):
                        linea["ubicacion_tabla"] = page_analysis["lineas"][l_idx].get("ubicacion_tabla", {})
                        lines_updated += 1
            
            logging.info(f"Table information added to {lines_updated} lines")
            
        except Exception as e:
            logging.error(f"Error adding table info to lines: {e}")
            import traceback
            logging.error(traceback.format_exc())
        
    def _clean(self):
        """
        Implements specific cleaning for evolution documents.
        1. Searches for "procedencia" and removes everything above it.
        2. Finds the most common x_inicio and removes lines outside that range.
        3. For lines with multiple spans, keeps only the rightmost span.
        4. NEW: Adds table info to each line using PDFLineAnalyzer.
        """

        if not self.structured_text:
            logging.error(f"No structured text available for {self.file_path}")
            return
        
        # NEW: Analyze tables BEFORE cleaning to add info to each line
        self._agregar_info_tabla_a_lineas()
        
        try:
            # Create a copy of structured_text to modify
            cleaned_structured_text = {
                "archivo": self.structured_text["archivo"],
                "total_paginas": self.structured_text["total_paginas"],
                "metadatos": self.structured_text["metadatos"],
                "paginas": []
            }
            
            # Copy pages initially
            for pagina in self.structured_text["paginas"]:
                cleaned_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": pagina["lineas"].copy()  # Initial copy of all lines
                }
                cleaned_structured_text["paginas"].append(cleaned_page)
            
            # Update structured_text with the initial copy
            self.structured_text = cleaned_structured_text
            
            # ========== NEW FUNCTIONALITY: Filter by PROCEDENCIA ==========
            
            # Create a global list of all lines with their original position
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
            
            # Search for "procedencia" in all lines
            procedencia_idx = None
            for i, line_info in enumerate(all_lines_with_position):
                if "procedencia" in line_info["texto"]:
                    procedencia_idx = i
                    logging.info(f"Found 'procedencia' at global position {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                    break
            
            if procedencia_idx is None:
                error_msg = f"Word 'procedencia' not found in document {self.file_path}"
                logging.error(error_msg)
                raise ValueError(error_msg)
            
            # Remove everything above procedencia
            lines_removed_by_cut = 0
            
            # Create new structure without lines above the cut
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
                        # Keep this line
                        filtered_page["lineas"].append(linea)
                    else:
                        # Remove this line
                        lines_removed_by_cut += 1
                        logging.debug(f"Removing line due to procedencia cut: '{linea.get('texto_completo', '')[:50]}...'")
                    
                    global_line_counter += 1
                
                # Only add pages that have lines remaining
                if filtered_page["lineas"]:
                    filtered_page["total_lineas_restantes"] = len(filtered_page["lineas"])
                    filtered_pages.append(filtered_page)
            
            # Update the structure
            self.structured_text["paginas"] = filtered_pages
            logging.info(f"Removed {lines_removed_by_cut} lines due to procedencia cut")
            
            # ========== END PROCEDENCIA SEARCH ==========
            
            # ========== SPAN HANDLING: Keep the rightmost span ==========
            
            lines_processed_spans = 0
            
            for pagina in self.structured_text["paginas"]:
                for linea in pagina["lineas"]:
                    spans_detallados = linea.get("spans_detallados", [])
                    
                    if len(spans_detallados) > 1:
                        # Find span with greatest x_inicio (further right)
                        span_mas_derecha = None
                        max_x_inicio = float('-inf')
                        
                        for span in spans_detallados:
                            x_inicio_span = span.get("posicion", {}).get("x0", 0)
                            if x_inicio_span > max_x_inicio:
                                max_x_inicio = x_inicio_span
                                span_mas_derecha = span
                        
                        if span_mas_derecha:
                            # Replace spans_detallados with only the rightmost span
                            linea["spans_detallados"] = [span_mas_derecha]
                            # Update texto_completo with selected span text
                            linea["texto_completo"] = span_mas_derecha.get("texto", "")
                            # IMPORTANT: Update line position mapping from span
                            span_posicion = span_mas_derecha.get("posicion", {})
                            if span_posicion:
                                linea["posicion"].update({
                                    "x_inicio": span_posicion.get("x0", linea["posicion"].get("x_inicio", 0)),
                                    "x_final": span_posicion.get("x1", linea["posicion"].get("x_final", 0)),
                                    "y_superior": span_posicion.get("y0", linea["posicion"].get("y_superior", 0)),
                                    "y_inferior": span_posicion.get("y1", linea["posicion"].get("y_inferior", 0))
                                })
                            # NEW: Also update line style with selected span style
                            span_estilo = span_mas_derecha.get("estilos", {})
                            if span_estilo:
                                linea["formato_principal"]["estilos"] = span_estilo.copy()

                            
                            lines_processed_spans += 1
                            logging.debug(f"Processed line with multiple spans, kept rightmost: '{linea['texto_completo'][:50]}...'")
            
            logging.info(f"Processed {lines_processed_spans} lines with multiple spans, kept the rightmost span")
                        
            # ========== END SPAN HANDLING ==========
            
            # ========== NEW FUNCTIONALITY: Filter by x_inicio_comun (PLUS AND MINUS) ==========
            
            # Collect all x_inicio values from remaining lines
            all_x_inicio_values = []
            tolerance = 8.0  # Tolerance to group similar x_inicio values
            
            for pagina in self.structured_text["paginas"]:
                for linea in pagina["lineas"]:
                    x_inicio = linea.get("posicion", {}).get("x_inicio")
                    if x_inicio is not None:
                        all_x_inicio_values.append(x_inicio)
            
            if not all_x_inicio_values:
                logging.warning(f"No x_inicio values found for {self.file_path}")
            else:
                # Group similar values using tolerance
                grouped_x_values = {}
                
                for x_val in all_x_inicio_values:
                    # Check if a similar group already exists
                    found_group = None
                    for group_key in grouped_x_values.keys():
                        if abs(x_val - group_key) <= tolerance:
                            found_group = group_key
                            break
                    
                    if found_group is not None:
                        grouped_x_values[found_group].append(x_val)
                    else:
                        grouped_x_values[x_val] = [x_val]
                
                # Find the most common group (x_inicio_comun)
                most_common_group = max(grouped_x_values.items(), key=lambda item: len(item[1]))
                x_inicio_comun = most_common_group[0]  # Use group key as reference
                frequency = len(most_common_group[1])
                
                logging.info(f"x_inicio_comun found: {x_inicio_comun:.2f} (frequency: {frequency})")
                
                # Second cleaning: Remove lines whose x_inicio is OUTSIDE the range (plus AND minus)
                lines_removed_count = 0
                
                for pagina in self.structured_text["paginas"]:
                    filtered_lines = []
                    
                    for linea in pagina["lineas"]:
                        x_inicio = linea.get("posicion", {}).get("x_inicio", 0)
                        
                        # Keep lines whose x_inicio is within common range (with tolerance)
                        if abs(x_inicio - x_inicio_comun) <= tolerance:
                            filtered_lines.append(linea)
                        else:
                            lines_removed_count += 1
                            logging.debug(f"Removing line due to x_inicio out of range: '{linea.get('texto_completo', '')[:50]}...' (x_inicio: {x_inicio:.2f}, difference: {abs(x_inicio - x_inicio_comun):.2f})")
                    
                    # Update page lines
                    pagina["lineas"] = filtered_lines
                    pagina["total_lineas_restantes"] = len(filtered_lines)
                
                logging.info(f"Removed {lines_removed_count} lines due to x_inicio outside common range (±{tolerance} of {x_inicio_comun:.2f})")
            
            # ========== END NEW FUNCTIONALITY x_inicio ==========
            
            # Optional: Also clean plain text by removing corresponding lines
            if self.text:
                # Reconstruct plain text with remaining lines
                clean_text_lines = []
                for pagina in self.structured_text["paginas"]:
                    for linea in pagina["lineas"]:
                        if linea.get("texto_completo"):
                            clean_text_lines.append(linea["texto_completo"])
                
                self.text = "\n".join(clean_text_lines)
            
            logging.info(f"Final cleaning completed for {self.file_path}")
            
        except Exception as e:
            logging.error(f"Error cleaning structured text for {self.file_path}: {e}")
            # In case of error, keep original text
            pass

        # Cleaning by substrings (original logic)
        substrings_to_remove = ["Pág", "Page", "Pag", "http", "fdo", "Fdo", "Jaén, a"]
        self.cleaned_structured_text, lines_removed = clean_structured_text(self.structured_text, substrings_to_remove)

    def _analyze_tables(self):
        """
        Analyzes tables in the PDF using PDFLineAnalyzer.
        Stores table information for later use.
        """
        try:
            logging.info(f"Analyzing tables in {self.file_path}")
            analyzer = PDFLineAnalyzer(self.file_path)
            analysis = analyzer.analyze_full_document()
            analyzer.close()
            
            # Store full analysis
            self.table_analysis = analysis
            
            # Extract table information
            self.tables_info = []
            for page in analysis.get("paginas", []):
                for table in page.get("tablas", []):
                    self.tables_info.append({
                        "pagina": page["pagina"],
                        "tabla": table
                    })
            
            logging.info(f"Found {len(self.tables_info)} table(s) in {self.file_path}")
            return self.table_analysis
            
        except Exception as e:
            logging.error(f"Error analyzing tables in {self.file_path}: {e}")
            self.table_analysis = None
            self.tables_info = []
            return None
    
    def _map_sections_to_table_cells(self):
        """
        Maps EACH SECTION to its cell using table location info ALREADY present in lines.
        
        ROBUST NEW APPROACH:
        - No text comparisons.
        - Uses ubicacion_tabla info already in each line.
        - For each section, examines its lines and determines which cell they belong to.
        - Assigns section to cell where MAJORITY of its lines reside.
        - Detects multi-page sections and saves cell merges.
        """
        if not hasattr(self, 'sections') or not self.sections:
            logging.warning("No sections available for mapping")
            return
        
        # Track which section types are already in each cell
        tipos_por_celda = {}  # celda_key -> set(tipos)
        
        # Save cell merges: when a section spans multiple pages,
        # cells from subsequent pages are merged with the first page cell.
        self.celda_fusiones = {}  # celda_secundaria (fila, pag) -> celda_principal (fila, pag)
        
        # For each section, determine its cell based on ORIGINAL lines
        for section in self.sections:
            section_name = section.get("seccion", "")
            section_body = section.get("cuerpo", "").strip()
            
            if not section_body:
                section["celda_info"] = {"en_tabla": False}
                logging.debug(f"Section '{section_name}' has no content")
                continue
            
            # Extract section type
            section_type = self._extraer_tipo_seccion(section_name)
            
            # Get REFERENCES to original lines (which have ubicacion_tabla)
            line_refs = section.get("line_refs", [])
            
            if not line_refs:
                section["celda_info"] = {"en_tabla": False}
                logging.debug(f"Section '{section_name}' has no line references")
                continue
            
            # Count which cells this section's lines reside in
            celda_counts = {}  # celda_key -> (count, celda_info)
            
            for linea_ref in line_refs:
                # Get ubicacion_tabla DIRECTLY from original line
                ubicacion_tabla = linea_ref.get("ubicacion_tabla")
                
                if ubicacion_tabla and ubicacion_tabla.get("ubicacion") == "dentro_tabla":
                    # Get page: first from ubicacion_tabla, then from _pagina_original, or default 1
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
            
            # Find cell with most lines from this section
            if celda_counts:
                logging.debug(f"Section '{section_name}': {len(celda_counts)} candidate cell(s)")
                
                # NOTE: In evolution, we allow multiple sections in the same cell
                # without filtering by type, as it's common for Evolution and Clinical Judgment
                # to share the same medical record row.
                celdas_disponibles = celda_counts
                
                if celdas_disponibles:
                    # Sort by: 1) Page (ascending - first page first)
                    #          2) Line count (descending - most lines first)
                    sorted_celdas = sorted(celdas_disponibles.items(), 
                                         key=lambda x: (
                                             x[0][3],  # Page (index 3 in celda_key)
                                             -x[1]["count"]  # Negative for descending order
                                         ))
                    
                    best_celda_key, best_data = sorted_celdas[0]
                    celda_info = best_data["celda_info"]
                    line_count = best_data["count"]
                    
                    # Assign the cell
                    section["celda_info"] = celda_info
                    
                    # Register type in cell
                    if best_celda_key not in tipos_por_celda:
                        tipos_por_celda[best_celda_key] = set()
                    tipos_por_celda[best_celda_key].add(section_type)
                    
                    tipos_str = ", ".join(tipos_por_celda[best_celda_key])
                    
                    # NEW: Detect if section spans multiple pages
                    # and save cell merges
                    paginas_unicas = set(key[3] for key in celdas_disponibles.keys())
                    if len(paginas_unicas) > 1:
                        # Principal cell (chosen one - first page)
                        celda_principal = (celda_info['fila'], celda_info['pagina'])
                        
                        # Merge all cells from other pages with principal
                        for celda_key in celdas_disponibles.keys():
                            if celda_key != best_celda_key:
                                # Secondary cell (row, page) -> Principal cell (row, page)
                                celda_secundaria = (celda_key[1], celda_key[3])  # (row, page)
                                
                                # Only merge if no merge already exists for this secondary cell
                                if celda_secundaria not in self.celda_fusiones:
                                    self.celda_fusiones[celda_secundaria] = celda_principal
                                    logging.info(f"   🔗 Cell merge: "
                                               f"Row {celda_secundaria[0] + 1} Pag {celda_secundaria[1]} "
                                               f"→ Row {celda_principal[0] + 1} Pag {celda_principal[1]}")
                    
                    multi_page_info = f", Page {celda_info['pagina']}" if len(paginas_unicas) > 1 else ""
                    
                    logging.info(f"✓ Section '{section_name}' -> "
                                       f"Table {celda_info['tabla_id']}, "
                                       f"Row {celda_info['fila'] + 1}, "
                               f"Column {celda_info['columna'] + 1}{multi_page_info} "
                               f"({line_count}/{len(line_refs)} lines) "
                               f"[Types: {tipos_str}]")
                else:
                    # All cells already have this type
                    section["celda_info"] = {"en_tabla": False}
                    logging.warning(f"⚠️ Section '{section_name}': all {len(celda_counts)} found cell(s) already have type '{section_type}'")
                    logging.warning(f"   Skipped cells: {list(celda_counts.keys())}")
            else:
                # No lines found in table
                section["celda_info"] = {"en_tabla": False}
                logging.warning(f"⚠️ Section '{section_name}' ({len(line_refs)} lines) has no lines mapped to tables")
                logging.warning(f"   Lines are outside tables or missing ubicacion_tabla")
        
        # Validation
        self._validar_mapeo_celdas()
    
    def _encontrar_ubicacion_linea(self, texto_linea):
        """
        Searches for a text line in cleaned_structured_text and returns its ubicacion_tabla.
        
        Uses exact search first, then partial search if necessary.
        
        Args:
            texto_linea (str): Text of line to search
            
        Returns:
            dict: ubicacion_tabla info, or None if not found
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text:
            return None
        
        texto_buscar = texto_linea.strip().lower()
        
        if not texto_buscar or len(texto_buscar) < 2:
            return None
        
        # STEP 1: Exact search
        for pagina in self.cleaned_structured_text.get("paginas", []):
            for linea in pagina.get("lineas", []):
                texto_linea_actual = linea.get("texto_completo", "").strip().lower()
                
                if texto_buscar == texto_linea_actual:
                    # Found! Return its ubicacion_tabla
                    ubicacion = linea.get("ubicacion_tabla")
                    if ubicacion:
                        # Add page if missing
                        if "pagina" not in ubicacion:
                            ubicacion["pagina"] = pagina["pagina"]
                        return ubicacion
        
        # STEP 2: Partial search (one line contains the other)
        # Only for lines long enough (>10 characters)
        if len(texto_buscar) > 10:
            for pagina in self.cleaned_structured_text.get("paginas", []):
                for linea in pagina.get("lineas", []):
                    texto_linea_actual = linea.get("texto_completo", "").strip().lower()
                    
                    # If one contains the other with >90% similarity
                    if texto_buscar in texto_linea_actual or texto_linea_actual in texto_buscar:
                        if len(texto_linea_actual) > 0:
                            ratio = min(len(texto_buscar), len(texto_linea_actual)) / max(len(texto_buscar), len(texto_linea_actual))
                            if ratio >= 0.9:  # 90% similarity
                                ubicacion = linea.get("ubicacion_tabla")
                                if ubicacion:
                                    if "pagina" not in ubicacion:
                                        ubicacion["pagina"] = pagina["pagina"]
                                    return ubicacion
        
        return None
    
    def _extraer_tipo_seccion(self, section_name):
        """
        Extracts section type by removing trailing number.
        
        Examples:
            "Juicio_Clinico_1" -> "Juicio_Clinico"
            "Exploracion_2" -> "Exploracion"
        
        Args:
            section_name (str): Full section name with number
            
        Returns:
            str: Section type without number
        """
        if not section_name:
            return ""
        
        # Split by last underscore
        parts = section_name.rsplit('_', 1)
        
        if len(parts) == 2:
            # Check if last part is a number
            try:
                int(parts[1])
                # It's a number, return only first part
                return parts[0]
            except ValueError:
                # Not a number, return full name
                return section_name
        
        # No underscore or only one, return full
        return section_name
    
    def _normalizar_texto(self, texto):
        """
        Normalizes text by removing line breaks, multiple spaces, and special characters.
        
        Args:
            texto (str): Text to normalize
            
        Returns:
            str: Normalized text
        """
        import re
        
        if not texto:
            return ""
        
        # Lowercase
        texto = texto.lower()
        
        # Remove line breaks and tabs
        texto = texto.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Remove multiple whitespaces
        texto = re.sub(r'\s+', ' ', texto)
        
        # Strip leading/trailing spaces
        texto = texto.strip()
        
        return texto
    
    def _calcular_similitud_textos(self, texto1, texto2):
        """
        Calculates similarity between two normalized texts STRICTLY and BIDIRECTIONALLY.
        
        Algorithm considers:
        1. Exact character similarity (using lengths).
        2. Word similarity in BOTH directions.
        3. Penalty if extra words exist in either text.
        
        Args:
            texto1 (str): First text (normalized) - section text
            texto2 (str): Second text (normalized) - cell text
            
        Returns:
            float: Similarity between 0.0 and 1.0
        """
        if not texto1 or not texto2:
            return 0.0
        
        # Case 1: Exact match
        if texto1 == texto2:
            return 1.0
        
        # Case 2: Bidirectional character similarity
        # Only if one text is contained in other AND difference is small
        if texto1 in texto2:
            ratio_caracteres = len(texto1) / len(texto2)
            if ratio_caracteres >= 0.9:
                return ratio_caracteres
        
        if texto2 in texto1:
            ratio_caracteres = len(texto2) / len(texto1)
            if ratio_caracteres >= 0.9:
                return ratio_caracteres
        
        # Case 3: Word similarity - STRICT BIDIRECTIONAL ALGORITHM
        palabras1 = set(texto1.split())
        palabras2 = set(texto2.split())
        
        if not palabras1 or not palabras2:
            return 0.0
        
        # Common words
        palabras_comunes = palabras1.intersection(palabras2)
        
        if not palabras_comunes:
            return 0.0
        
        # Calculate coverage in BOTH directions
        cobertura_texto1 = len(palabras_comunes) / len(palabras1)  # Words of texto1 in texto2?
        cobertura_texto2 = len(palabras_comunes) / len(palabras2)  # Words of texto2 in texto1?
        
        # KEY: Use AVERAGE of both coverages (bidirectional)
        similitud_bidireccional = (cobertura_texto1 + cobertura_texto2) / 2.0
        
        # Also calculate Jaccard index
        palabras_union = palabras1.union(palabras2)
        similitud_jaccard = len(palabras_comunes) / len(palabras_union)
        
        # Return MIN (strictest) between bidirectional and Jaccard
        return min(similitud_bidireccional, similitud_jaccard)
    
    def _calcular_similitud_linea(self, linea_seccion, linea_tabla):
        """
        Calculates similarity between a section line and a table line.
        Uses multiple criteria to improve matching precision.
        
        Args:
            linea_seccion (str): Section body line
            linea_tabla (str): Line found in table analysis
            
        Returns:
            float: Similarity score
        """
        # Normalize texts
        linea_sec_lower = linea_seccion.lower().strip()
        linea_tab_lower = linea_tabla.lower().strip()
        
        # Criterion 1: Exact match (max score)
        if linea_sec_lower == linea_tab_lower:
            return 2.0
        
        # Criterion 2: One line completely contains the other
        if len(linea_sec_lower) > 15 or len(linea_tab_lower) > 15:
            if linea_sec_lower in linea_tab_lower or linea_tab_lower in linea_sec_lower:
                min_len = min(len(linea_sec_lower), len(linea_tab_lower))
                if min_len > 30:
                    return 1.5
                elif min_len > 15:
                    return 1.2
            else:
                    return 0.8
        
        # Criterion 3: Match of significant words
        palabras_seccion = set(p for p in linea_sec_lower.split() if len(p) > 3)
        palabras_tabla = set(p for p in linea_tab_lower.split() if len(p) > 3)
        
        if palabras_seccion and palabras_tabla:
            palabras_comunes = palabras_seccion.intersection(palabras_tabla)
            
            if palabras_comunes:
                ratio = len(palabras_comunes) / min(len(palabras_seccion), len(palabras_tabla))
                if ratio >= 0.7:
                    return 1.0
                elif ratio >= 0.5:
                    return 0.6
                elif len(palabras_comunes) >= 3:
                    return 0.4
        
        # Criterion 4: Partial similarity for short lines
        if len(linea_sec_lower) <= 15 and len(linea_tab_lower) <= 15:
            if linea_sec_lower == linea_tab_lower:
                return 2.0
            elif linea_sec_lower in linea_tab_lower or linea_tab_lower in linea_sec_lower:
                longer = max(len(linea_sec_lower), len(linea_tab_lower))
                shorter = min(len(linea_sec_lower), len(linea_tab_lower))
                if shorter / longer > 0.8:
                    return 0.5
        
        return 0.0
    
    def _validar_mapeo_celdas(self):
        """
        Validates section-to-cell mapping and reports issues.
        
        IMPORTANT: A cell CAN have multiple sections of DIFFERENT types.
        What MUST NOT happen is multiple sections of the SAME type sharing a cell.
        """
        if not hasattr(self, 'sections') or not self.sections:
            return
        
        # Group sections by cell
        celda_to_sections = {}
        
        for section in self.sections:
            celda_info = section.get('celda_info', {})
            
            if celda_info.get('en_tabla', False):
                # Unique cell key
                celda_key = (
                    celda_info.get('tabla_id'),
                    celda_info.get('fila'),
                    celda_info.get('columna'),
                    celda_info.get('pagina')
                )
                
                if celda_key not in celda_to_sections:
                    celda_to_sections[celda_key] = []
                
                celda_to_sections[celda_key].append(section.get('seccion', ''))
        
        # Detect cells with multiple sections of the SAME type
        problemas_detectados = False
        for celda_key, secciones in celda_to_sections.items():
            if len(secciones) > 1:
                # Extract section types (without number)
                tipos_seccion = {}  # type -> [sections with that type]
                
                for sec_name in secciones:
                    tipo = self._extraer_tipo_seccion(sec_name)
                    if tipo not in tipos_seccion:
                        tipos_seccion[tipo] = []
                    tipos_seccion[tipo].append(sec_name)
                
                # Check if any type has multiple instances
                tipos_duplicados = {tipo: secs for tipo, secs in tipos_seccion.items() if len(secs) > 1}
                
                if tipos_duplicados:
                    # ERROR: Multiple sections of SAME type in a cell
                    problemas_detectados = True
                    tabla_id, fila, columna, pagina = celda_key
                    logging.warning(
                        f"❌ ERROR: Multiple sections of SAME type in a cell:\n"
                        f"  Cell: Table {tabla_id}, Row {fila + 1}, Column {columna + 1}, Page {pagina}\n"
                    )
                    for tipo, secs in tipos_duplicados.items():
                        logging.warning(f"    Type '{tipo}': {', '.join(secs)}")
                elif len(tipos_seccion) > 1:
                    # OK: Multiple sections of DIFFERENT types (valid)
                    tabla_id, fila, columna, pagina = celda_key
                    tipos_str = ', '.join(tipos_seccion.keys())
                    logging.info(
                        f"✓ Correctly shared cell: "
                        f"Table {tabla_id}, Row {fila + 1}, Column {columna + 1} "
                        f"contains types: {tipos_str}"
                    )
        
        if problemas_detectados:
            logging.warning(
                "⚠️ ERRORS detected in cell mapping. "
                "Multiple sections of same type MUST NOT share a cell. "
                "Review previous warnings."
            )
        else:
            logging.info("✅ Mapping validation completed: no conflicts detected")
    
    def _join_from_index(self, text_list, start_index):
        """
        Utility method to join elements of a list from a specific index.
        
        Args:
            text_list (list): List of strings
            start_index (int): Index from which to start joining
            
        Returns:
            str: Joined string
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
        Specific validation for evolution sheets.
        """
        super()._validate_result()
        
    def _extract_sections(self):
        """
        Extracts bold sections from structured_text for evolution documents.
        Each section starts with bold text and continues until the next bold text.
        If sections have same name, they are numbered sequentially.
        
        Returns:
            list: List of dictionaries with format:
                {'seccion': str, 'cuerpo': str, 'numero_seccion': int}
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text or "paginas" not in self.cleaned_structured_text:
            logging.warning(f"No cleaned structured text available for section extraction in {self.file_path}")
            return []
        
        sections = []
        current_section = None
        current_body_lines = []  # List of TEXTS for body
        current_body_line_refs = []  # List of REFERENCES to original lines
        section_counters = {}  # To keep count of sections with same name
        
        # Create global list of all lines
        # IMPORTANT: Add page number to each line to distinguish them
        all_lines = []
        for pagina in self.cleaned_structured_text["paginas"]:
            page_num = pagina["pagina"]
            for linea in pagina["lineas"]:
                # Ensure ubicacion_tabla has the page
                if "ubicacion_tabla" in linea:
                    if "pagina" not in linea["ubicacion_tabla"]:
                        linea["ubicacion_tabla"]["pagina"] = page_num
                # Also store page directly in line for reference
                linea["_pagina_original"] = page_num
                all_lines.append(linea)

        def get_bold_info(linea):
            """
            Extracts bold text information from a line.
            Returns: (is_bold, bold_text)
            """
            texto_completo = linea.get("texto_completo", "").strip()
            spans_detallados = linea.get("spans_detallados", [])
            
            # Check main format of the line
            formato_principal = linea.get("formato_principal", {})
            estilos_principales = formato_principal.get("estilos", [])
            
            if "negrita" in estilos_principales:
                return True, texto_completo
            
            # If not bold in main format, check detailed spans
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
            
            # Heuristic criteria to detect possible titles/sections
            if not spans_detallados and texto_completo:
                if (len(texto_completo) < 50 and 
                    (texto_completo.isupper() or 
                    texto_completo.endswith(':') or
                    all(word[0].isupper() for word in texto_completo.split() if word))):
                    return True, texto_completo
            
            return False, ""
        
        def normalize_section_name(name):
            """
            Normalizes section name by removing accents and replacing spaces with underscores.
            
            Args:
                name (str): Original section name
                
            Returns:
                str: Normalized name
            """
            # Map for removing accents
            tildes_map = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
                'ñ': 'n', 'Ñ': 'N'
            }
            
            # Remove accents
            normalized = name
            for tilde, normal in tildes_map.items():
                normalized = normalized.replace(tilde, normal)
            
            # Replace spaces with underscores
            normalized = normalized.replace(' ', '_')
            
            return normalized
        
        def save_current_section():
            """Saves current section to data structure."""
            nonlocal current_section, current_body_lines, current_body_line_refs, sections
            
            if current_section is not None:
                current_section['cuerpo'] = '\n'.join(current_body_lines).strip()
                current_section['line_refs'] = current_body_line_refs.copy()  # Save original line references
                sections.append(current_section)
                current_section = None
                current_body_lines = []
                current_body_line_refs = []
        
        # Process all lines
        for i, linea in enumerate(all_lines):
            texto_completo = linea.get("texto_completo", "").strip()
            is_bold, bold_text = get_bold_info(linea)
            
            if is_bold and bold_text.strip():
                # Save previous section before creating new one
                save_current_section()
                
                # Process section name
                section_name = bold_text.strip()
                
                # Clean section name (remove trailing ':' if exists)
                if section_name.endswith(':'):
                    section_name = section_name[:-1].strip()
                
                # Normalize name (remove accents and spaces)
                normalized_section_name = normalize_section_name(section_name)
                
                # Count sections with same normalized name
                if normalized_section_name in section_counters:
                    section_counters[normalized_section_name] += 1
                else:
                    section_counters[normalized_section_name] = 1
                
                # Create unique name with counter
                unique_section_name = f"{normalized_section_name}_{section_counters[normalized_section_name]}"
                
                # Create new section
                current_section = {
                    'seccion': unique_section_name.strip().rstrip(":").strip(),
                    'cuerpo': '',
                    'numero_seccion': section_counters[normalized_section_name],
                    'nombre_original': section_name
                }
                current_body_lines = []
                current_body_line_refs = []
                
                logging.debug(f"New section found: '{unique_section_name}' (original: '{section_name}')")
                
            elif texto_completo:
                # Add line to current section body
                if current_section is not None:
                    current_body_lines.append(texto_completo)
                    current_body_line_refs.append(linea)  # Save original line reference
        
        # Don't forget last section
        save_current_section()
        
        # Save sections as instance attribute
        self.sections = sections
        logging.info(f"Extracted {len(sections)} sections from {self.file_path}")
        
        # Log summary of found sections
        section_summary = {}
        for section in sections:
            original_name = section['nombre_original']
            if original_name in section_summary:
                section_summary[original_name] += 1
            else:
                section_summary[original_name] = 1
        
        logging.info(f"Section summary: {section_summary}")

        # ========== MAP TO TABLES ==========
        # Tables were already analyzed in _clean() and each line has ubicacion_tabla.
        # Now we just map sections to their cells.
        self._map_sections_to_table_cells()
        # ========== END MAPPING ==========

        self.args = sections
        
        return sections

    def print_sections(self):
        """
        Prints extracted sections in readable format.
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        if not sections:
            print(f"No bold sections found in {self.file_path}")
            return
        
        print(f"\n{self.file_path}")
        print(f"Found {len(sections)} sections:")
        print("=" * 80)
        
        for i, section in enumerate(sections, 1):
            print(f"\nSECTION {i}: {section['seccion']}")
            print(f"Original name: {section['nombre_original']}")
            print(f"Repetition number: {section['numero_seccion']}")
            print("-" * 60)
            
            if section['cuerpo'].strip():
                print(f"BODY:")
                print(section['cuerpo'])
            else:
                print("(No content)")
            
            print("=" * 80)

    def get_sections_summary(self):
        """
        Gets a summary of the extracted section structure.
        
        Returns:
            dict: Summary with section statistics
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        total_sections = len(sections)
        unique_section_names = set(s['nombre_original'] for s in sections)
        
        # Count repetitions by name
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
        Generates a folder structure with .txt files for each evolution section.
        Sections are grouped by original name.
        
        Args:
            output_dir (str|Path): Base directory for structure.
                                 If None, created alongside source file.
        
        Returns:
            Path: Root path of created directory
        """
        import re
        from pathlib import Path
        
        try:
            # Ensure sections are extracted
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determine output directory
            if output_dir is None:
                source_path = Path(self.file_path)
                output_dir = source_path.parent / f"{source_path.stem}_evolucion_structured"
            else:
                output_dir = Path(output_dir)
            
            # Create base directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Group sections by original name
            grouped_sections = {}
            for section in self.sections:
                original_name = section['nombre_original']
                if original_name not in grouped_sections:
                    grouped_sections[original_name] = []
                grouped_sections[original_name].append(section)
            
            # Process each group
            for original_name, sections_group in grouped_sections.items():
                # Sanitize original name
                sanitized_name = self._sanitize_filename(original_name)
                
                if len(sections_group) == 1:
                    # If single occurrence, create simple file
                    section_file = output_dir / f"{sanitized_name}.txt"
                    section = sections_group[0]
                    
                    with open(section_file, 'w', encoding='utf-8') as f:
                        f.write(section['cuerpo'])
                    logging.info(f"Created file: {section_file}")
                else:
                    # If multiple occurrences, create folder
                    section_dir = output_dir / sanitized_name
                    section_dir.mkdir(exist_ok=True)
                    
                    for section in sections_group:
                        section_file = section_dir / f"{section['seccion']}.txt"
                        if section['cuerpo'].strip():
                            with open(section_file, 'w', encoding='utf-8') as f:
                                f.write(section['cuerpo'])
                            logging.info(f"Created file: {section_file}")
            

            # ========== GENERATE FOLDER STRUCTURE BY ROW ==========
            # ALWAYS generate grouping by row
            self._generar_carpetas_por_celda(output_dir)
            # ========== END ROW GROUPING ==========
            
            logging.info(f"Structured text generated at: {output_dir}")
            return output_dir
        
        except Exception as e:
            logging.error(f"Error generating structured text for {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def _generar_carpetas_por_celda(self, base_output_dir):
        """
        POST-PROCESSING: Groups sections sharing same row and page.
        IGNORES column, only considers (row, page).
        
        Args:
            base_output_dir (Path): Base directory for folders
        """
        try:
            from collections import defaultdict
            
            base_output_dir = Path(base_output_dir)
            
            # Group sections by row and page (IGNORE column)
            secciones_por_celda = defaultdict(list)
            
            for section in self.sections:
                celda_info = section.get('celda_info', {})
                
                if celda_info.get('en_tabla', False):
                    # Unique key with row and page (NO column)
                    celda_key = (
                        celda_info.get('fila', 0),
                        celda_info.get('pagina', 1)
                    )
                    
                    secciones_por_celda[celda_key].append(section)
            
            # NEW: Apply cell merges
            if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
                logging.info(f"Applying {len(self.celda_fusiones)} cell merges...")
                
                for celda_secundaria, celda_principal in self.celda_fusiones.items():
                    if celda_secundaria in secciones_por_celda:
                        # Move all sections from secondary to principal cell
                        secciones_a_mover = secciones_por_celda[celda_secundaria]
                        
                        if secciones_a_mover:
                            logging.info(f"   🔗 Merging: "
                                       f"Row {celda_secundaria[0] + 1} Pag {celda_secundaria[1]} "
                                       f"→ Row {celda_principal[0] + 1} Pag {celda_principal[1]} "
                                       f"({len(secciones_a_mover)} sections)")
                            
                            # Add to principal cell
                            secciones_por_celda[celda_principal].extend(secciones_a_mover)
                            
                            # Remove secondary cell
                            del secciones_por_celda[celda_secundaria]
            
            if not secciones_por_celda:
                logging.info("No sections in tables to group by cell")
                return
            
            # Create directory for grouped row folders
            celdas_dir = base_output_dir / "registros"
            celdas_dir.mkdir(exist_ok=True)
            
            # Create one folder per row having sections
            celda_to_registro = {}
            registro_counter = 1
            for celda_key, secciones in sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0])):
                fila, pagina = celda_key
                
                # Folder name using sequential counter
                carpeta_nombre = f"registro_{registro_counter}"
                celda_to_registro[celda_key] = registro_counter
                celda_dir = celdas_dir / carpeta_nombre
                celda_dir.mkdir(exist_ok=True)
                registro_counter += 1
                
                # Create consolidated file with all sections
                todas_secciones_path = celda_dir / "TODAS_LAS_SECCIONES.txt"
                with open(todas_secciones_path, 'w', encoding='utf-8') as f:
                    f.write(f"ALL SECTIONS IN THIS ROW\n")
                    f.write(f"Row {fila + 1}, Page {pagina}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"Total sections: {len(secciones)}\n\n")
                    
                    for section in secciones:
                        celda_info = section.get('celda_info', {})
                        col = celda_info.get('columna', -1)
                        tabla_id = celda_info.get('tabla_id', 0)
                        
                        f.write("\n" + "=" * 60 + "\n")
                        f.write(f"Column: {col + 1}, Table ID: {tabla_id}\n")
                        f.write("=" * 60 + "\n\n")
                        f.write(section.get('cuerpo', ''))
                        f.write("\n\n")
                
                # Create individual file for each section
                for section in secciones:
                    section_name = section.get('seccion', '')
                    sanitized_name = self._sanitize_filename(section_name)
                    section_path = celda_dir / f"{sanitized_name}.txt"
                    
                    with open(section_path, 'w', encoding='utf-8') as f:
                        f.write(section.get('cuerpo', ''))
                
                logging.info(f"Record folder created: {carpeta_nombre} with {len(secciones)} section(s)")
            
            # Create grouping summary file
            resumen_path = celdas_dir / "RESUMEN_AGRUPACION.txt"
            with open(resumen_path, 'w', encoding='utf-8') as f:
                f.write("GROUPING SUMMARY BY ROW AND PAGE\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Total rows with sections: {len(secciones_por_celda)}\n")
                f.write(f"Total grouped sections: {sum(len(s) for s in secciones_por_celda.values())}\n\n")
                f.write("NOTE: Sections are grouped by ROW and PAGE (ignores column)\n\n")
                
                # Cell merge info
                if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
                    f.write("🔗 APPLIED CELL MERGES:\n")
                    f.write("-" * 70 + "\n")
                    f.write("When a section spans multiple pages, subsequent page sections\n")
                    f.write("are merged with the first page.\n\n")
                    for celda_sec, celda_prin in sorted(self.celda_fusiones.items()):
                        f.write(f"  • Row {celda_sec[0] + 1} Pag {celda_sec[1]} "
                              f"→ Row {celda_prin[0] + 1} Pag {celda_prin[1]}\n")
                    f.write("\n")
                
                f.write("GROUPING DETAIL:\n")
                f.write("-" * 70 + "\n\n")
                
                for celda_key, secciones in sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0])):
                    fila, pagina = celda_key
                    
                    columnas = set()
                    for s in secciones:
                        col = s.get('celda_info', {}).get('columna')
                        if col is not None:
                            columnas.add(col)
                    
                    registro_num = celda_to_registro.get(celda_key, 0)
                    
                    f.write(f"Row {fila + 1}, Page {pagina}\n")
                    f.write(f"  Folder: registro_{registro_num}\n")
                    if columnas:
                        f.write(f"  Present columns: {', '.join(map(lambda x: str(x+1), sorted(columnas)))}\n")
                    f.write(f"  Sections ({len(secciones)}):\n")
                    for s in secciones:
                        col = s.get('celda_info', {}).get('columna', -1)
                        f.write(f"    - {s.get('seccion', '')} ({s.get('nombre_original', '')}) [Col {col + 1}]\n")
                    f.write("\n")
            
            logging.info(f"Generated {len(secciones_por_celda)} record folders in {celdas_dir}")
            
        except Exception as e:
            logging.error(f"Error generating folders by cell: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _sanitize_filename(self, filename):
        """
        Sanitizes a name for use as a filename.
        
        Args:
            filename (str): Original name
        
        Returns:
            str: Sanitized name
        """
        import re
        
        # Remove forbidden characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Replace spaces and dashes with underscores
        sanitized = re.sub(r'[\s\-–—]+', '_', sanitized)
        
        # Remove trailing punctuation
        sanitized = sanitized.strip('.:,;')
        
        # Remove extra punctuation
        sanitized = re.sub(r'[/()]', '', sanitized)
        
        # Limit length
        if len(sanitized) > 80:
            sanitized = sanitized[:80]
        
        # Capitalize each word
        sanitized = '_'.join(word.capitalize() for word in sanitized.split('_') if word)
        
        return sanitized or "Untitled"
    
    def get_md(self, output_path=None, case_id=None):
        """
        Generates and saves evolution sheet in Markdown format.
        
        Args:
            output_path (str|Path): Path to save MD file. 
            case_id (str): Optional case identifier
        
        Returns:
            Path|None: Path of generated MD file, or None if error
        """
        from pathlib import Path
        
        try:
            # Ensure sections are extracted
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determine output path
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_evolucion.md"
            else:
                output_path = Path(output_path)
            
            # Create directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get source filename
            file_name = Path(self.file_path).name
            
            # Generate Markdown content
            md_content = self._generate_markdown_content(case_id, file_name)
            
            # Save file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logging.info(f"Evolution MD report generated for {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating evolution MD file for {self.file_path}: {e}")
            return None
    
    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Generates Markdown content from extracted sections.
        Groups sections by record (cell/row).
        """
        from collections import defaultdict
        
        md_content = "# EVOLUTION SHEET\n\n"
        
        if case_id:
            md_content += f"**Case Number:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Source File:** {file_name}\n\n"
        
        # Detected tables info
        if hasattr(self, 'tables_info') and self.tables_info:
            md_content += f"**Detected tables:** {len(self.tables_info)}\n\n"
            
            if hasattr(self, 'sections') and self.sections:
                secciones_en_tabla = sum(1 for s in self.sections if s.get('celda_info', {}).get('en_tabla', False))
                if secciones_en_tabla > 0:
                    md_content += f"**Sections located in tables:** {secciones_en_tabla}\n\n"
        
        md_content += "---\n\n"
        
        # Group sections by record (cell/row)
        secciones_por_celda = defaultdict(list)
        secciones_sin_celda = []
        
        for section in self.sections:
            celda_info = section.get('celda_info', {})
            
            if celda_info.get('en_tabla', False):
                celda_key = (
                    celda_info.get('fila', 0),
                    celda_info.get('pagina', 1)
                )
                secciones_por_celda[celda_key].append(section)
            else:
                secciones_sin_celda.append(section)
        
        # Apply cell merges
        if hasattr(self, 'celda_fusiones') and self.celda_fusiones:
            for celda_secundaria, celda_principal in self.celda_fusiones.items():
                if celda_secundaria in secciones_por_celda:
                    secciones_por_celda[celda_principal].extend(secciones_por_celda[celda_secundaria])
                    del secciones_por_celda[celda_secundaria]
        
        # Sort records: page first, then row
        registros_ordenados = sorted(secciones_por_celda.items(), key=lambda x: (x[0][1], x[0][0]))
        
        # Generate content per record
        registro_counter = 1
        for celda_key, secciones in registros_ordenados:
            fila, pagina = celda_key
            
            # Record title
            md_content += f"## RECORD {registro_counter}\n\n"
            
            md_content += "\n"
            
            # List all sections in this record
            for section in secciones:
                section_name = section.get('nombre_original', section.get('seccion', ''))
                md_content += f"### {section_name}\n\n"
                
                if section['cuerpo'].strip():
                    md_content += f"{section['cuerpo']}\n\n"
            
            md_content += "---\n\n"
            registro_counter += 1
        
        md_content += "*Automatically generated report*\n"
        
        return md_content