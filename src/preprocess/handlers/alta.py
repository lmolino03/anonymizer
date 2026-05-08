from preprocess.core.base_processor import BaseProcessor
import logging
import json
from utils.utils import clean_structured_text

import re
import logging
from pathlib import Path
import pypandoc

class ProcessorAlta(BaseProcessor):
    """Specific processor for hospital discharge reports."""
    
    def __init__(self, file_path):
        """
        Initializes the discharge processor.
        
        Args:
            file_path (str): Path to the discharge PDF file
        """
        super().__init__(file_path)
    
    def _clean(self):
        """
        Implements specific cleaning for discharge documents.
        Filters lines and removes segments based on common x_inicio position.
        """

        if not self.structured_text:
            logging.error(f"No structured text available for {self.file_path}")
            return
        
        try:
            # Create a copy of structured_text to modify
            cleaned_structured_text = {
                "archivo": self.structured_text["archivo"],
                "total_paginas": self.structured_text["total_paginas"],
                "metadatos": self.structured_text["metadatos"],
                "paginas": []
            }
            
            # Process each page
            for pagina in self.structured_text["paginas"]:
                cleaned_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": []
                }
                
                # Copy all lines for initial processing
                for linea in pagina["lineas"]:
                    cleaned_page["lineas"].append(linea)

                cleaned_page["total_lineas_restantes"] = len(cleaned_page["lineas"])
                cleaned_structured_text["paginas"].append(cleaned_page)

            
            # Update structured_text with the first cleaning results
            self.structured_text = cleaned_structured_text
            
            logging.info(f"Cleaned structured text for {self.file_path}. Removed lines with spans.")
            
            # ========== NEW FUNCTIONALITY: Filter by x_inicio_comun ==========
            
            # Collect all x_inicio values from cleaned lines
            all_x_inicio_values = []
            tolerance = 22.0  # Tolerance to group similar x_inicio values
            
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
                    # Find if a similar group already exists
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
                
                # Second cleaning: Remove lines whose x_inicio is greater than x_inicio_comun
                lines_removed_count = 0
                
                for pagina in self.structured_text["paginas"]:
                    filtered_lines = []
                    
                    for linea in pagina["lineas"]:
                        x_inicio = linea.get("posicion", {}).get("x_inicio", 0)
                        
                        # Keep lines whose x_inicio is less than or equal to common (with tolerance)
                        if x_inicio <= x_inicio_comun + tolerance:
                            filtered_lines.append(linea)
                        else:
                            lines_removed_count += 1
                            logging.debug(f"Removing line due to x_inicio > x_comun: '{linea.get('texto_completo', '')[:50]}...' (x_inicio: {x_inicio:.2f})")
                    
                    # Update page lines
                    pagina["lineas"] = filtered_lines
                    pagina["total_lineas_restantes"] = len(filtered_lines)
                
                logging.info(f"Removed {lines_removed_count} lines due to x_inicio > x_inicio_comun ({x_inicio_comun:.2f})")
            
            # ========== END NEW FUNCTIONALITY ==========
        
            # ========== NEW FILTER: Remove lines containing only "a." ==========
            
            lines_removed_by_a_filter = 0
            
            for pagina in self.structured_text["paginas"]:
                filtered_lines = []
                
                for linea in pagina["lineas"]:
                    n_text = linea.get("texto_completo", "")
                    texto_limpio = n_text.strip().rstrip(":").strip().lower()
                    
                    # Check if line contains only "a."
                    if texto_limpio == "a.":
                        lines_removed_by_a_filter += 1
                        logging.debug(f"Removing line containing only 'a.': '{linea.get('texto_completo', '')}'")
                    else:
                        filtered_lines.append(linea)
                
                # Update page lines
                pagina["lineas"] = filtered_lines
                pagina["total_lineas_restantes"] = len(filtered_lines)
            
            logging.info(f"Removed {lines_removed_by_a_filter} lines containing only 'a.'")
            
            # ========== END "a." FILTER ==========

            
            # ========== SEARCH AND CUT BY ANTECEDENTS/MOTIVE ==========
            
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
            
            # Search for "antecedentes" in all lines
            antecedentes_idx = None
            for i, line_info in enumerate(all_lines_with_position):
                if "antecedentes" in line_info["texto"]:
                    antecedentes_idx = i
                    logging.info(f"Found 'antecedentes' at global index {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                    break
            
            # Determine cut line
            cut_line_idx = None
            
            if antecedentes_idx is not None:
                # Search for "motivo" above antecedents (closest)
                motivo_idx = None
                for i in range(antecedentes_idx - 1, -1, -1):  # Search backwards from antecedents
                    if "motivo" in all_lines_with_position[i]["texto"].lower():
                        motivo_idx = i
                        logging.info(f"Found 'motivo' at global index {i} (above antecedents): '{all_lines_with_position[i]['linea'].get('texto_completo', '')[:50]}...'")
                        break
                
                if motivo_idx is not None:
                    # Remove everything above motivo
                    cut_line_idx = motivo_idx
                    logging.info(f"Will remove everything above 'motivo' (index {motivo_idx})")
                else:
                    # Motivo not found, remove everything above antecedents
                    cut_line_idx = antecedentes_idx
                    logging.info(f"'motivo' not found above 'antecedentes'. Will remove everything above 'antecedentes' (index {antecedentes_idx})")
            
            else:
                # Antecedents not found, search for motivo directly
                motivo_idx = None
                for i, line_info in enumerate(all_lines_with_position):
                    if "motivo" in line_info["texto"]:
                        motivo_idx = i
                        logging.info(f"'antecedentes' not found. Found 'motivo' at global index {i}: '{line_info['linea'].get('texto_completo', '')[:50]}...'")
                        break
                
                if motivo_idx is not None:
                    # Remove everything above motivo
                    cut_line_idx = motivo_idx
                    logging.info(f"Will remove everything above 'motivo' (index {motivo_idx})")
                else:
                    # Neither antecedents nor motivo found - ERROR
                    error_msg = f"Words 'antecedentes' or 'motivo' not found in document {self.file_path}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
            
            # Perform cut if a cut line was determined
            if cut_line_idx is not None:
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
                        if global_line_counter >= cut_line_idx:
                            # Keep this line
                            filtered_page["lineas"].append(linea)
                        else:
                            # Remove this line
                            lines_removed_by_cut += 1
                            logging.debug(f"Removing line due to antecedents/motive cut: '{linea.get('texto_completo', '')[:50]}...'")
                        
                        global_line_counter += 1
                    
                    # Only add pages that have lines remaining
                    if filtered_page["lineas"]:
                        filtered_page["total_lineas_restantes"] = len(filtered_page["lineas"])
                        filtered_pages.append(filtered_page)
                
                # Update the structure
                self.structured_text["paginas"] = filtered_pages
                
                logging.info(f"Removed {lines_removed_by_cut} lines due to antecedents/motive cut")
            
            # ========== END ANTECEDENTS/MOTIVE SEARCH ==========
            
            # Optional: Also clean plain text by removing corresponding lines
            if self.text:
                # Reconstruct plain text without removed lines
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
        substrings_to_remove = ["Pág", "Page", "Pag", "http", "fdo", "Fdo", "Jaén", "NHC:"]
        self.cleaned_structured_text, lines_removed = clean_structured_text(self.structured_text, substrings_to_remove)

    
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
        Specific validation for discharge documents.
        """
        super()._validate_result()

        self.print_bold_sections()
        self.get_sections_summary()


    def _extract_sections(self):
        """
        Extracts bold sections and their subsequent content from structured_text,
        including support for nested sections (max 2 levels).
        
        Returns:
            list: List of dictionaries with format:
                - For main sections: {'seccion': str, 'cuerpo': str, 'nivel': 1, 'subsecciones': []}
                - For subsections: {'seccion': str, 'cuerpo': str, 'nivel': 2, 'x_posicion': float}
        """
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text or "paginas" not in self.cleaned_structured_text:
            logging.warning(f"No cleaned structured text available for section extraction in {self.file_path}")
            return []
        
        sections = []
        current_main_section = None
        current_subsection = None
        current_body_lines = []
        main_section_x_start = None  # X position of the main section
        
        # Create global list of all lines
        all_lines = []

        for pagina in self.cleaned_structured_text["paginas"]:
            for linea in pagina["lineas"]:
                all_lines.append(linea)

        
        def get_bold_info(linea):
            """
            Extracts bold text information from a line.
            Returns: (is_bold, bold_text, x_start_position)
            """
            texto_completo = linea.get("texto_completo", "").strip()
            spans_detallados = linea.get("spans_detallados", [])
            x_start = linea.get("posicion", {}).get("x_inicio", 0)
            
            # Check main format of the line
            formato_principal = linea.get("formato_principal", {})
            estilos_principales = formato_principal.get("estilos", [])
            
            if "bold" in estilos_principales:
                return True, texto_completo, x_start
            
            # If not bold in main format, check detailed spans
            bold_text = ""
            min_x_start = float('inf')
            has_bold = False
            
            if spans_detallados:
                for span in spans_detallados:
                    estilos_span = span.get("estilos", [])
                    if "bold" in estilos_span:
                        has_bold = True
                        bold_text += span.get("texto", "")
                        span_x = span.get("posicion", {}).get("x0", 0)
                        min_x_start = min(min_x_start, span_x)
                
                if has_bold:
                    return True, bold_text.strip(), min_x_start if min_x_start != float('inf') else x_start
            
            # Heuristic criteria to detect possible titles/sections
            if texto_completo:
                if (len(texto_completo) < 50 and 
                    (texto_completo.isupper() or 
                    texto_completo.endswith(':') or
                    all(word[0].isupper() for word in texto_completo.split() if word))):
                    return True, texto_completo, x_start
            
            return False, "", x_start
        
        def save_current_section():
            """Saves current section or subsection to data structure."""
            nonlocal current_main_section, current_subsection, current_body_lines, sections
            
            if current_subsection is not None:
                # Saving a subsection
                current_subsection['cuerpo'] = '\n'.join(current_body_lines).strip()
                
                # Find current main section and add the subsection
                if sections and sections[-1]['nivel'] == 1:
                    sections[-1]['subsecciones'].append(current_subsection)
                else:
                    # If no main section exists, create a temporary one
                    temp_main = {
                        'seccion': f"Main section for: {current_subsection['seccion']}",
                        'cuerpo': '',
                        'nivel': 1,
                        'subsecciones': [current_subsection],
                        'x_posicion': current_subsection['x_posicion'] - 10  # Assume it's further left
                    }
                    sections.append(temp_main)
                
                current_subsection = None
                
            elif current_main_section is not None:
                # Saving a main section
                current_main_section['cuerpo'] = '\n'.join(current_body_lines).strip()
                sections.append(current_main_section)
                current_main_section = None
        
        # Process all lines
        for i, linea in enumerate(all_lines):
            texto_completo = linea.get("texto_completo", "").strip()
            is_bold, bold_text, x_start = get_bold_info(linea)
            
            if is_bold and bold_text.strip():
                # Determine if main section or subsection
                is_subsection = False
                
                if main_section_x_start is not None:
                    # Compare X positions with previous main section
                    if x_start > main_section_x_start:
                        is_subsection = True
                
                # Save previous section before creating new one
                save_current_section()
                
                if is_subsection:
                    # Create new subsection
                    current_subsection = {
                        'seccion': bold_text.strip().rstrip(":").strip(),
                        'cuerpo': '',
                        'nivel': 2,
                        'x_posicion': x_start
                    }


                    current_body_lines = []
                else:
                    # Create new main section
                    current_main_section = {
                        'seccion': bold_text.strip().rstrip(":").strip(),
                        'cuerpo': '',
                        'nivel': 1,
                        'subsecciones': [],
                        'x_posicion': x_start
                    }
                    main_section_x_start = x_start
                    current_body_lines = []
                    current_subsection = None  # Reset current subsection
                
            elif texto_completo:
                # Add line to current section/subsection body
                if current_subsection is not None or current_main_section is not None:
                    current_body_lines.append(texto_completo)
        
        # Don't forget last section
        save_current_section()
        
        # Save sections as instance attribute
        self.sections = sections
        
        # Convert sections to format compatible with previous scripts
        self._convert_sections_to_args()
        
        logging.info(f"Extracted {len(sections)} main sections with nested subsections from {self.file_path}")
        
        return sections

    def _convert_sections_to_args(self):
        """
        Converts extracted sections to original script format.
        Maps specific sections and assigns them in correct order.
        """
        # Initialize variables as None
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
        
        # Mapping of section names to variables (case-insensitive)
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
        
        # Store found contents
        found_sections = {}
        
        # Iterate over extracted sections
        for section in self.sections:
            if section['nivel'] == 1:
                section_name = section['seccion'].lower().strip()
                
                # Search for match in mapping
                for key, var_name in section_mapping.items():
                    if key in section_name:
                        # Combine main section body with subsections
                        content = section['cuerpo']
                        
                        # Add subsections if they exist
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
        
        # Assign found values
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
        
        # Create tuple in specified order
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
        Prints extracted sections in readable format, including nested subsections.
        """
        if not hasattr(self, 'sections') or not self.sections:
            sections = self._extract_sections()
        else:
            sections = self.sections
        
        if not sections:
            print(f"No bold sections found in {self.file_path}")
            return
        
        print(f"\n{self.file_path}")
        print(f"Found {len(sections)} main sections:")
        print("=" * 80)
        
        section_counter = 1
        for section in sections:
            if section['nivel'] == 1:
                print(f"\nMAIN SECTION {section_counter}: {section['seccion']}")
                print(f"X Position: {section.get('x_posicion', 'N/A')}")
                print("-" * 60)
                
                if section['cuerpo'].strip():
                    print(f"BODY:")
                    print(section['cuerpo'])
                    print()
                
                # Show subsections if they exist
                if section.get('subsecciones'):
                    print(f"SUBSECTIONS ({len(section['subsecciones'])}):")
                    for i, subsection in enumerate(section['subsecciones'], 1):
                        print(f"  {section_counter}.{i} {subsection['seccion']}")
                        print(f"      X Position: {subsection.get('x_posicion', 'N/A')}")
                        if subsection['cuerpo'].strip():
                            # Indent subsection body
                            subsection_body = '\n'.join(['      ' + line for line in subsection['cuerpo'].split('\n')])
                            print(f"      BODY:")
                            print(subsection_body)
                        print()
                
                section_counter += 1
                print("=" * 80)

    def get_sections_summary(self):
        """
        Gets a summary of extracted section structure.
        
        Returns:
            dict: Summary with section statistics
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
        Returns arguments in compatible format.
        
        Returns:
            tuple: (motivo, antecedentes, enfermedad, pruebas_complementarias, evolucion,
                    intervencion, juicio, actuacion, tratamiento, revisiones)
        """
        if not hasattr(self, 'args'):
            self._extract_sections()
        
        return self.args
    

    def get_md(self, output_path=None, case_id=None):
        """
        Generates and saves report in Markdown format.
        
        Args:
            output_path (str|Path): Path to save MD file. 
            case_id (str): Optional case identifier
        
        Returns:
            Path|None: Path of generated MD file, or None if error
        """
        try:
            # Ensure sections are extracted
            if not hasattr(self, 'args'):
                self._extract_sections()
            
            # Determine output path
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_informe.md"
            else:
                output_path = Path(output_path)
            
            # Create directory if missing
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get source filename
            file_name = Path(self.file_path).name
            
            # Generate Markdown content
            md_content = self._generate_markdown_content(case_id, file_name)
            
            # Save the file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logging.info(f"MD report generated for {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating MD file for {self.file_path}: {e}")
            return None


    def get_pdf(self, output_path=None, case_id=None):
        """
        Generates and saves report in PDF format.
        
        Args:
            output_path (str|Path): Path to save PDF. 
            case_id (str): Optional case identifier
        
        Returns:
            Path|None: Path of generated PDF, or None if error
        """
        try:
            # Ensure sections are extracted
            if not hasattr(self, 'args'):
                self._extract_sections()
            
            # Determine output path
            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_informe.pdf"
            else:
                output_path = Path(output_path)
            
            # Create directory
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get source filename
            file_name = Path(self.file_path).name
            
            # Generate Markdown content
            md_content = self._generate_markdown_content(case_id, file_name)
            
            # Save temporary Markdown
            temp_md = output_path.parent / f"{output_path.stem}_temp.md"
            with open(temp_md, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Convert to PDF using pypandoc
            pypandoc.convert_file(
                str(temp_md),
                'pdf',
                outputfile=str(output_path),
                extra_args=[
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=2.5cm',
                    '-V', 'fontsize=11pt',
                    '-V', 'mainfont=Arial',
                    '--standalone'
                ]
            )
            
            # Remove temporary file
            temp_md.unlink()
            
            logging.info(f"PDF report generated for {self.file_path}: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating PDF for {self.file_path}: {e}")
            return None


    def _clean_separator_lines(self, content):
        """
        Removes lines containing only dashes (visual separators).
        
        Args:
            content (str): Markdown content to clean
        
        Returns:
            str: Content without separator lines
        """
        if not content:
            return ""
        
        # Split into lines
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Check if line contains only dashes and spaces
            if re.match(r'^\s*-{3,}\s*$', line):
                cleaned_lines.append("\n")
                continue
            
            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)


    def _merge_wrapped_lines(self, content):
        """
        Merges lines separated only for visual formatting.
        Detects lines not ending with strong punctuation and joins with next.
        
        Args:
            content (str): Content with possible unnecessary line breaks
        
        Returns:
            str: Content with appropriately merged lines
        """
        if not content:
            return ""
        
        # Punctuation indicating sentence/paragraph end
        end_punctuation = {'.', '!', '?', ':', ';'}
        
        # Patterns indicating valid new line start
        list_markers = ['-', '•', '*', '·']
        
        lines = content.split('\n')
        merged_lines = []
        current_line = ""
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # If line is empty, it's a new paragraph
            if not stripped:
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                merged_lines.append("")
                continue
            
            # If start of list or numbering
            is_list_item = any(stripped.startswith(marker) for marker in list_markers)
            is_numbered = len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)-'
            
            if is_list_item or is_numbered:
                if current_line:
                    merged_lines.append(current_line)
                current_line = stripped
                continue
            
            # If current line has content
            if current_line:
                # Check if previous line ends with strong punctuation
                last_char = current_line.rstrip()[-1] if current_line.rstrip() else ''
                
                if last_char in end_punctuation:
                    merged_lines.append(current_line)
                    current_line = stripped
                else:
                    current_line += " " + stripped
            else:
                current_line = stripped
        
        # Don't forget last line
        if current_line:
            merged_lines.append(current_line)
        
        return '\n'.join(merged_lines)


    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Generates Markdown content from extracted arguments.
        """
        (motivo, antecedentes, enfermedad, pruebas_complementarias, evolucion,
        intervencion, juicio, actuacion, tratamiento, revisiones) = self.args
        
        md_content = "# HOSPITAL DISCHARGE REPORT\n\n"
        
        if case_id:
            md_content += f"**Case Number:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Source File:** {file_name}\n\n"
        
        md_content += "---\n\n"
        
        sections_data = [
            (motivo, "Reason for Admission"),
            (antecedentes, "Background"),
            (enfermedad, "Current History"),
            (pruebas_complementarias, "Complementary Tests"),
            (evolucion, "Evolution"),
            (intervencion, "Procedures and Surgical Intervention"),
            (juicio, "Clinical Judgment and Diagnoses"),
            (actuacion, "Therapeutic Plan"),
            (tratamiento, "Treatment"),
            (revisiones, "Follow-ups")
        ]
        
        for content, section_name in sections_data:
            if content and content.strip() and content != 'None':
                # CLEANING ORDER:
                cleaned_content = self._clean_separator_lines(content.strip())
                merged_content = self._merge_wrapped_lines(cleaned_content)
                formatted_content = self._format_markdown_linebreaks(merged_content)
                
                md_content += f"## {section_name}\n\n{formatted_content}\n\n"
        
        md_content += "---\n\n*Automatically generated report*\n"
        
        return md_content


    def _format_markdown_linebreaks(self, content):
        """
        Formats content so Markdown preserves line breaks.
        Adds two spaces at end of each line or converts simple breaks to double.
        
        Args:
            content (str): Content to format
        
        Returns:
            str: Formatted content
        """
        if not content:
            return ""
        
        # Split into lines
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:
                # If line ends with strong punctuation, add extra line
                if stripped.endswith(('.', ':', '?', '!')):
                    formatted_lines.append(line)
                    formatted_lines.append('')
                # If list line
                elif stripped.startswith(('-', '*', '•')) or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)-'):
                    formatted_lines.append(line + '  ')
                else:
                    formatted_lines.append(line + '  ')
            else:
                # Preserve empty lines
                formatted_lines.append('')
        
        return '\n'.join(formatted_lines)


    def _clean_markdown_content(self, content, is_first_section=False):
        """
        Cleans markdown content by removing redundant headers.
        Private helper method.
        
        Args:
            content (str): Content to clean
            is_first_section (bool): If first section
        
        Returns:
            str: Cleaned content
        """
        if not content:
            return ""
        
        # Remove level 2 headers containing section name
        content = re.sub(r'^##\s+.*?\n', '', content, flags=re.MULTILINE)
        
        # Split into lines
        lines = content.split('\n')
        
        # If not first section, remove first line with text
        if not is_first_section and lines:
            for i, line in enumerate(lines):
                if line.strip():
                    lines = lines[i+1:]
                    break
        
        content = '\n'.join(lines)
        
        return content.strip()
    
    def get_structured_text(self, output_dir=None):
        """
        Generates folder structure with .txt files for each section.
        Works directly with self.sections to preserve original hierarchy.
        
        Args:
            output_dir (str|Path): Base directory for structure.
        
        Returns:
            Path: Root path of created directory
        """
        try:
            # Ensure sections are extracted
            if not hasattr(self, 'sections') or not self.sections:
                self._extract_sections()
            
            # Determine output directory
            if output_dir is None:
                source_path = Path(self.file_path)
                output_dir = source_path.parent / f"{source_path.stem}_structured"
            else:
                output_dir = Path(output_dir)
            
            # Create base directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Counter for section numbering
            section_counter = 1
            
            # Process each main section
            for section in self.sections:
                if section['nivel'] != 1:
                    continue
                
                # Sanitize section name
                section_name = self._sanitize_filename(section['seccion'])
                
                # Check for subsections
                has_subsections = section.get('subsecciones') and len(section['subsecciones']) > 0
                
                if has_subsections:
                    # Create folder for section with subsections
                    section_dir = output_dir / f"{section_name}"
                    section_dir.mkdir(exist_ok=True)
                    
                    # Save main content if exists
                    if section['cuerpo'].strip():
                        main_content = self._clean_separator_lines(section['cuerpo'])
                        main_content = self._merge_wrapped_lines(main_content)
                        main_file = section_dir / "_principal.txt"
                        
                        with open(main_file, 'w', encoding='utf-8') as f:
                            f.write(main_content)
                        logging.info(f"Created main file: {main_file}")
                    
                    # Save each subsection
                    for subsection in section['subsecciones']:
                        if subsection['cuerpo'].strip():
                            # Sanitize subsection name
                            subsec_name = self._sanitize_filename(subsection['seccion'])
                            subsec_content = self._clean_separator_lines(subsection['cuerpo'])
                            subsec_content = self._merge_wrapped_lines(subsec_content)
                            
                            subsec_file = section_dir / f"{subsec_name}.txt"
                            with open(subsec_file, 'w', encoding='utf-8') as f:
                                f.write(subsec_content)
                            logging.info(f"Created subsection: {subsec_file}")
                    
                    logging.info(f"Created folder with subsections: {section_dir}")
                
                else:
                    # Create single file for section without subsections
                    content = self._clean_separator_lines(section['cuerpo'])
                    content = self._merge_wrapped_lines(content)
                    
                    if content.strip():
                        section_file = output_dir / f"{section_name}.txt"
                        with open(section_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        logging.info(f"Created file: {section_file}")
                
                section_counter += 1
            
            # Create README file with info
            readme_path = output_dir / "README.txt"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"GENERATED DISCHARGE REPORT STRUCTURE\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Source file: {self.file_path}\n")
                f.write(f"Total main sections: {len([s for s in self.sections if s['nivel'] == 1])}\n")
                f.write(f"Total subsections: {sum(len(s.get('subsecciones', [])) for s in self.sections if s['nivel'] == 1)}\n\n")
                
                f.write("CONTENT STRUCTURE:\n")
                f.write("-" * 60 + "\n\n")
                
                counter = 1
                for section in self.sections:
                    if section['nivel'] == 1:
                        section_name = section['seccion']
                        subsections = section.get('subsecciones', [])
                        
                        if subsections:
                            f.write(f"{counter:02d}. {section_name}/ (folder)\n")
                            if section['cuerpo'].strip():
                                f.write(f"    - _principal.txt\n")
                            for subsec in subsections:
                                f.write(f"    - {subsec['seccion']}.txt\n")
                        else:
                            f.write(f"{counter:02d}. {section_name}.txt\n")
                        
                        counter += 1
            
            logging.info(f"Structured text generated at: {output_dir}")
            return output_dir
        
        except Exception as e:
            logging.error(f"Error generating structured text for {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None


    def _sanitize_filename(self, filename):
        """
        Sanitizes a name for use as a filename.
        
        Args:
            filename (str): Original name
        
        Returns:
            str: Sanitized name
        """
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
