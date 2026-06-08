from preprocess.core.base_processor import BaseProcessor
from models.gammagrafia import HojaGammagrafia
from utils.utils import clean_structured_text
import logging
import re
import json
from pathlib import Path


class ProcessorGammagrafia(BaseProcessor):
    def __init__(self, file_path):
        super().__init__(file_path)

    def _clean(self):
       
        if not self.structured_text:
            logging.error(f"Structured text is empty for file{self.file_path}")
            return

        try:
            cleaned_structured_text = {
                "archivo": self.structured_text["archivo"],
                "total_paginas": self.structured_text["total_paginas"],
                "metadatos": self.structured_text["metadatos"],
                "paginas": []
            }

            for pagina in self.structured_text["paginas"]:
                cleaned_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": pagina["lineas"].copy() 
                }
                cleaned_structured_text["paginas"].append(cleaned_page)

            self.structured_text = cleaned_structured_text

            all_lines_with_position = [] # empty list

            for page_idx, pagina in enumerate(self.structured_text["paginas"]): # page_idx = nºpágina, pagina is the dictionary with the information of that page
                for line_idx, linea in enumerate(pagina["lineas"]): # line_idx = nºlínea inside of that page, linea is the dictionary with the text
                    all_lines_with_position.append({
                        "linea": linea,
                        "page_idx": page_idx,
                        "line_idx": line_idx,
                        "global_idx": len(all_lines_with_position),  # global position of the line in the whole document
                        "texto": linea.get("texto_completo", "").lower() # dont distinc between mayus and minus
                    })

            corte_idx = None

            for i, line_info in enumerate(all_lines_with_position): # i = global line, line_info is the dictionary with the line and its position
                texto = line_info["texto"]
                if "datos de informe" in texto:
                    corte_idx = i
                    logging.info(
                        f"Found 'datos de informe' at global line {i}: '{line_info['linea'].get('texto_completo', '')[:50]}'"
                    )
                    break

            if corte_idx is None:
                error_msg = f"No 'datos de informe' was found in {self.file_path}"
                logging.error(error_msg)
                raise ValueError(error_msg)

            lines_removed = 0
            global_counter = 0
            filtered_pages = []

            for page_idx, pagina in enumerate(self.structured_text["paginas"]): # page_idx = nºpágina, pagina is the dictionary with the information of that page
                filtered_page = {
                    "pagina": pagina["pagina"],
                    "dimensiones": pagina["dimensiones"],
                    "lineas": [] # here we will store the lines that survive the cut
                }
                
                for linea in pagina["lineas"]:
                    if global_counter >= corte_idx:
                        # If this line is below the cut-off, we keep it
                        filtered_page["lineas"].append(linea)
                    else:
                        # If this line is above the cut-off, we remove it
                        lines_removed += 1
                        logging.debug(
                            f"Deleting header line: '{linea.get('texto_completo', '')[:50]}'"
                        )
                    global_counter += 1

                # If the page has any lines left after filtering, we keep it in the structure
                if filtered_page["lineas"]:
                    filtered_page["total_lineas_restantes"] = len(filtered_page["lineas"])
                    filtered_pages.append(filtered_page)

            # After processing all pages, we update the structured_text with the filtered pages
            self.structured_text["paginas"] = filtered_pages
            logging.info(f"Removed {lines_removed} header/patient data lines above the cut-off.")

            if self.text:
                clean_text_lines = []
                for pagina in self.structured_text["paginas"]:
                    for linea in pagina["lineas"]:
                        if linea.get("texto_completo"): # we check if the line has text to avoid adding empty lines
                            clean_text_lines.append(linea["texto_completo"])
                self.text = "\n".join(clean_text_lines) # join all the lines that survived the cut into a single text separated by line breaks

        except Exception as e:
            logging.error(f"Error cleaning the text of {self.file_path}: {e}")
        
        substrings_to_remove = [
            "Pág", "Page", "Pag", "http", "Fdo", "fdo", "Jaén", "NHC:", "DNI:", "NASS:", "Teléfono:", "Firmado", "Código de Informe:", "Informe Principal",
        ]

        for pagina in self.structured_text["paginas"]:
            for linea in pagina["lineas"]:
                texto_original = linea.get("texto_completo", "")
                # Found the line that contains both "fecha" and "exploración" 
                if "fecha" in texto_original.lower() and "exploración" in texto_original.lower():
                    # We remove the substring "Código" from that line
                    linea["texto_completo"] = texto_original.replace("Código", "")

        self.cleaned_structured_text, lines_removed = clean_structured_text(
            self.structured_text, substrings_to_remove
        )
        logging.info(f"Cleaning by substrings: eliminated {lines_removed} additional lines")

    def _extract_sections(self):
        # Extract sections based on bold text in the cleaned structured text.

        # Verify if we have clean text available to process
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text:
            logging.warning(f"There is no clean text available to extract sections in {self.file_path}")
            return []  # avoid the program to crash


        all_lines = []
        for pagina in self.cleaned_structured_text["paginas"]:
            for linea in pagina["lineas"]:
                all_lines.append(linea) # create a single list with the complete dictionary of the lines

        def es_titulo(linea):
            # Determine if a line is a title based on its formatting and content.

            texto = linea.get("texto_completo", "").strip() # text without line breaks and spaces at the beginning and end

            formato_principal = linea.get("formato_principal", {})
            estilos = formato_principal.get("estilos", [])
            if "bold" in estilos:
                return True, texto

            return False, ""

        sections = []          
        current_section = None 
        current_body = []

        def guardar_seccion_actual():
            nonlocal current_section, current_body
            if current_section is not None:
                current_section["cuerpo"] = "\n".join(current_body).strip() # save the body of the section as a single string
                sections.append(current_section) # add the section to the list of sections
                current_section = None # reset the current section to start a new one
                current_body = [] # reset the body for the next section

        for linea in all_lines:
            texto_completo = linea.get("texto_completo", "").strip() # save the text of the line without line breaks and spaces at the beginning and end
            es_tittulo, texto_titulo = es_titulo(linea) # check if the line is a title and get the text of the title if it is

            if es_tittulo and texto_titulo: # if the line is a title and has text, we start a new section
                guardar_seccion_actual() # we save the previous section before starting a new one
                current_section = {
                    "seccion": texto_titulo.strip().rstrip(":").strip(), # title without ":" at the end
                    "cuerpo": ""
                }
                current_body = []

            elif texto_completo and current_section is not None:
                # if it is normal text and we have a current section, we add it to the body of the current section
                current_body.append(texto_completo)

        guardar_seccion_actual() # save the last section after finishing the loop

        self.sections = sections
        logging.info(f"Extracted {len(sections)} sections from the report")

        self._convertir_secciones_a_args()

        return sections

    def _convertir_secciones_a_args(self):
       
        fecha_informe = None
        datos_clinicos = None
        exploraciones = None
        anatomias = None
        hallazgos = None
        conclusion = None
        recomendaciones = None

        section_mapping = {
            "fecha de informe": "fecha_de_informe",    
            "datos clínicos": "datos_clinicos", 
            "sospecha": "datos_clinicos",   
            "justificación": "datos_clinicos",  
            "exploraciones": "exploraciones", 
            "anatomías": "anatomias",      
            "hallazgos": "hallazgos",        
            "indicación": "conclusion",       
            "conclus": "conclusion",       
            "recomendaciones": "recomendaciones", 
        }

        found_sections = {}

        for section in self.sections:
            section_name = section["seccion"].lower().strip()

            for key, var_name in section_mapping.items(): # we check if any of the keys defined in the mapping is contained in the section name (case insensitive)
                if key in section_name: 
                    if var_name not in found_sections: # if the title is duplicated, we only take the first one and ignore the rest
                        content = section["cuerpo"].strip()
                        found_sections[var_name] = content if content else None
                    break 

        fecha_informe   = found_sections.get("fecha_de_informe")
        datos_clinicos  = found_sections.get("datos_clinicos")
        exploraciones   = found_sections.get("exploraciones")
        anatomias       = found_sections.get("anatomias")
        hallazgos       = found_sections.get("hallazgos")
        conclusion      = found_sections.get("conclusion")
        recomendaciones = found_sections.get("recomendaciones")

        self.args = (
            fecha_informe,
            datos_clinicos,
            exploraciones,
            anatomias,
            hallazgos,
            conclusion,
            recomendaciones
        )

        encontradas = sum(1 for x in self.args if x is not None)
        logging.info(f"Converted sections to args: {encontradas}/7 founds sections")

    def _validate_result(self):
      
        super()._validate_result()

        # Check if sections have been extracted into the args tuple
        if not hasattr(self, 'args'):
            logging.warning("No sections have been extracted from the report")
            return

        # Unpack only the critical clinical fields using placeholders
        _, _, _, _, hallazgos, conclusion, _ = self.args

        # Warn if vital medical text blocks are missing from the parsed data
        if hallazgos is None:
            logging.warning(f"WARNING: No 'Hallazgos' were found in {self.file_path}")
        if conclusion is None:
            logging.warning(f"WARNING: No 'Conclusión' was found in {self.file_path}")

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
                output_path = source_path.parent / f"{source_path.stem}_gammagrafia.md"
            else:
                output_path = Path(output_path)

            # Create directory if missing
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Get source filename
            file_name = Path(self.file_path).name

            # Generate Markdown content
            md_content = self._generate_markdown_content(case_id, file_name)

            # Save to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            logging.info(f"MD report generated for {self.file_path}: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Error generating MD file for {self.file_path}: {e}")
            return None
        
    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Generates Markdown content from extracted arguments.
        """
        (fecha_informe ,datos_clinicos, exploraciones, anatomias,
         hallazgos, conclusion, recomendaciones) = self.args

        md_content = "# GAMMAGRAFIA REPORT\n\n"

        if case_id:
            md_content += f"**Case Number:** {case_id}\n\n"
        if file_name:
            md_content += f"**Source File:** {file_name}\n\n"

        md_content += "---\n\n"

        sections_data = [
            (fecha_informe,   "Report Date"),
            (datos_clinicos,  "Clinical Data / Diagnostic Suspicions"),
            (exploraciones,   "Examinations Performed"),
            (anatomias,       "Anatomical Structures Studied"),
            (hallazgos,       "Findings"),
            (conclusion,      "Diagnostic Indication / Conclusion"),
            (recomendaciones, "Recommendations"),
        ]

        for content, section_name in sections_data:
            if content and content.strip() and content != "None":
                md_content += f"## {section_name}\n\n{content.strip()}\n\n"

        md_content += "---\n\n*Automatically generated report*\n"

        return md_content


    def _parsear_exploraciones_a_json(self, cuerpo):
      
        exploraciones = []

        lineas = [l.strip() for l in cuerpo.splitlines() if l.strip()]

        for linea in lineas:
            linea_lower = linea.lower()

            if "fecha" in linea_lower or "exploración" in linea_lower:
                continue

            patron_fecha = r"^((0[1-9]|[12][0-9]|3[01])\s/\s(0[1-9]|1[0-2])\s/\s\d{4})"
            patron = re.match(patron_fecha, linea)

            if patron:
                fecha_sola = patron.group(1)
                fecha = re.sub(r'\s*/\s*', '/', fecha_sola).strip()

                exploracion = linea[patron.end():].strip()

                exploraciones.append({
                    "fecha": fecha,
                    "exploracion": exploracion,
                    "codigo": ""
                })

        return exploraciones

    def get_structured_text(self, output_dir=None):
        """
        Generates folder structure with .txt files for each section.
        The 'Exploraciones Realizadas' section is saved as .json instead of .txt
        because it is a structured table (date, exploration, code).
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

            for section in self.sections:
                if section["cuerpo"].strip():
                    # Convert section name into a valid filename
                    file_name = re.sub(r'[<>:"/\\|?*\s]+', '_', section["seccion"])
                    file_name = file_name.strip('._')[:80] or "Sin_titulo"

                    # 'Exploraciones Realizadas' is a table → save as JSON
                    if "explorac" in section["seccion"].lower():
                        datos_json = self._parsear_exploraciones_a_json(section["cuerpo"])
                        if datos_json:
                            json_file = output_dir / f"{file_name}.json"
                            with open(json_file, 'w', encoding='utf-8') as f:
                                json.dump(datos_json, f, ensure_ascii=False, indent=4)
                            logging.info(f"JSON file created: {json_file}")

                    else:
                        # All other sections are saved as plain .txt
                        section_file = output_dir / f"{file_name}.txt"
                        with open(section_file, 'w', encoding='utf-8') as f:
                            f.write(section["cuerpo"])
                        logging.info(f"File created: {section_file}")

            logging.info(f"Structured text generated at: {output_dir}")
            return output_dir

        except Exception as e:
            logging.error(f"Error generating structured text for {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None