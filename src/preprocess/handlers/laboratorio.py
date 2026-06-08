from preprocess.core.base_processor import BaseProcessor
import logging
from pathlib import Path
import re

class ProcessorLaboratorio(BaseProcessor):
    """Specific processor for hospital laboratory documents."""
    
    def __init__(self, file_path):
        """
        Initializes the laboratory processor.
        
        Args:
            file_path (str): Path to the laboratory PDF file
        """
        super().__init__(file_path)
        
        # Variables requested to store each section
        self.inicio = ""
        self.hematologia_general = ""
        self.hemostasia_fibrinolisis = ""
        self.bioquimica_general = ""
        self.proteinas_especificas = ""
        self.vitaminas_sangre = ""
        
    def __getattr__(self, name):
        """
        Dynamically returns section content when requested via legacy attributes.
        """
        # Avoid infinite recursion during initialization/attributes check
        if name in ['sections', 'args', 'file_path', 'text', 'structured_text', 'cleaned_structured_text', 'cleaned_text', 'inicio', 'hematologia_general', 'hemostasia_fibrinolisis', 'bioquimica_general', 'proteinas_especificas', 'vitaminas_sangre']:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
        sections = getattr(self, 'sections', None)
        if sections:
            normalized_name = name.replace('_', ' ').lower()
            for s in sections:
                # Compare without accents or casing
                sec_name = s['seccion'].lower()
                accents = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n'}
                for k, v in accents.items():
                    sec_name = sec_name.replace(k, v)
                    normalized_name = normalized_name.replace(k, v)
                if normalized_name in sec_name:
                    return s['cuerpo']
                    
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        
    def _clean(self):
        """
        Cleans the text by removing the header, personal data, footers and validation signature.
        """
        if not self.text:
            return
            
        lines = self.text.split('\n')
        cleaned_lines = []
        start_collecting = False
        
        # Keywords that indicate a line contains personal or metadata that we want to remove
        personal_data_keywords = [
            "nombre", "nhc", "dni", "sexo", "fecha", "edad", "apellidos", "cip", "nuss", 
            "historia clinica", "historia clínica", "procedencia", "médico", "medico", 
            "habitación", "habitacion", "servicio", "cama", "dirección", "direccion", 
            "teléfono", "telefono", "perteneciente a", "página", "solicitante", "destinatario",
            "prof.:", "centro:", "nº petición:", "nº de muestra/laboratorio", "toma de muestras",
            "último resultado", "fecha del informe", "código sns:",
            "pruebas solicitadas", "valores referencia", "unidad", "resultado", "prueba"
        ]
        
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            
            # Start collecting when we reach the first section header: "HEMATOLOGÍA GENERAL"
            if not start_collecting:
                if "HEMATOLOGÍA GENERAL" in stripped_line.upper():
                    start_collecting = True
                    
            # Skip any line that contains personal info or is part of page footer/header
            line_lower = stripped_line.lower()
            is_personal = False
            for kw in personal_data_keywords:
                # Avoid removing actual values/units/tests unless they are exact headers
                if kw in ["prueba", "resultado", "unidad", "valores referencia"]:
                    if line_lower == kw or line_lower == f"-{kw}":
                        is_personal = True
                        break
                else:
                    if kw in line_lower:
                        is_personal = True
                        break
            
            # Stop if we reach the end validation signatures
            if "Validado por" in stripped_line:
                break
                
            if start_collecting and not is_personal:
                # Also remove numeric codes or date patterns (but keep shorter result numbers)
                if re.match(r'^\d{5,}$', stripped_line):
                    continue
                if re.match(r'^\d{2}/\d{2}/\d{4}.*$', stripped_line):
                    continue
                cleaned_lines.append(line) # Keep original line with casing/formatting
                
        self.cleaned_text = '\n'.join(cleaned_lines).strip()

    def _extract_sections(self):
        """
        Extracts specific sections, stores them in variables, and saves them to text files.
        """
        if not hasattr(self, 'cleaned_text') or not self.cleaned_text:
            self._clean()
            
        text = getattr(self, 'cleaned_text', "")
        
        if not text:
            logging.warning("No text to extract sections from.")
            return {}
            
        headers = [
            "HEMATOLOGÍA GENERAL",
            "HEMOSTASIA/FIBRINOLISIS",
            "BIOQUÍMICA GENERAL (SANGRE)",
            "PROTEÍNAS ESPECÍFICAS (SANGRE)",
            "VITAMINAS (SANGRE)"
        ]
        
        sections = {}
        
        # Extract sections
        current_text = text
        for i, header in enumerate(headers):
            start_idx = current_text.find(header)
            if start_idx != -1:
                if i + 1 < len(headers):
                    next_header = headers[i+1]
                    end_idx = current_text.find(next_header)
                    if end_idx == -1:
                        end_idx = len(current_text)
                else:
                    end_idx = len(current_text)
                    
                sections[header] = current_text[start_idx:end_idx].strip()
                
        # Parse and format tests in each section
        for header in headers:
            if header in sections:
                parsed_tests = self._parse_section_to_tests(header, sections[header])
                sections[header] = self._format_tests(parsed_tests)
                
        # Store in class variables as requested
        self.inicio = "" # No intro text remains after cleaning personal data
        self.hematologia_general = sections.get("HEMATOLOGÍA GENERAL", "")
        self.hemostasia_fibrinolisis = sections.get("HEMOSTASIA/FIBRINOLISIS", "")
        self.bioquimica_general = sections.get("BIOQUÍMICA GENERAL (SANGRE)", "")
        self.proteinas_especificas = sections.get("PROTEÍNAS ESPECÍFICAS (SANGRE)", "")
        self.vitaminas_sangre = sections.get("VITAMINAS (SANGRE)", "")
        
        # Guardar cada sección en un fichero de texto nuevo dentro de una carpeta llamada 'laboratorio'
        try:
            output_dir = Path(self.file_path).parent / "laboratorio"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for section_name, content in sections.items():
                if not content:
                    continue
                safe_name = section_name.replace("/", "_").replace(" ", "_")
                file_path = output_dir / f"{safe_name}.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            logging.info(f"Sections extracted and saved to: {output_dir}")
        except Exception as e:
            logging.error(f"Error writing section files: {e}")
            
        # Guardar en la variable self.sections para compatibilidad con get_structured_text
        self.sections = []
        
        headers_mapping = [
            ("HEMATOLOGÍA GENERAL", self.hematologia_general),
            ("HEMOSTASIA/FIBRINOLISIS", self.hemostasia_fibrinolisis),
            ("BIOQUÍMICA GENERAL (SANGRE)", self.bioquimica_general),
            ("PROTEÍNAS ESPECÍFICAS (SANGRE)", self.proteinas_especificas),
            ("VITAMINAS (SANGRE)", self.vitaminas_sangre)
        ]
        
        for name, content in headers_mapping:
            if content.strip():
                self.sections.append({
                    'seccion': name,
                    'cuerpo': content,
                    'nivel': 1,
                    'subsecciones': []
                })
                
        # For compatibility with BaseProcessor and Factory
        self.args = (sections,)
        return sections

    def _validate_result(self):
        super()._validate_result()

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
            
            # Process each main section
            for section in self.sections:
                if section['nivel'] != 1:
                    continue
                
                # Sanitize section name
                section_name = self._sanitize_filename(section['seccion'])
                
                # Create single file for section without subsections
                content = self._clean_separator_lines(section['cuerpo'])
                content = self._merge_wrapped_lines(content)
                
                if content.strip():
                    section_file = output_dir / f"{section_name}.txt"
                    with open(section_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logging.info(f"Created file: {section_file}")
            
            # Create README file with info
            readme_path = output_dir / "README.txt"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"GENERATED LABORATORY STRUCTURE\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Source file: {self.file_path}\n")
                f.write(f"Total main sections: {len([s for s in self.sections if s['nivel'] == 1])}\n\n")
                
                f.write("CONTENT STRUCTURE:\n")
                f.write("-" * 60 + "\n\n")
                
                counter = 1
                for section in self.sections:
                    if section['nivel'] == 1:
                        section_name = section['seccion']
                        f.write(f"{counter:02d}. {section_name}.txt\n")
                        counter += 1
            
            logging.info(f"Structured text generated at: {output_dir}")
            return output_dir
        
        except Exception as e:
            logging.error(f"Error generating structured text for {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None

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

    def _sanitize_filename(self, filename):
        """
        Sanitizes a name for use as a filename.
        """
        # Remove forbidden characters for filenames
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Replace spaces and dashes with underscores
        sanitized = re.sub(r'[\s\-–—]+', '_', sanitized)
        
        # Remove trailing punctuation
        sanitized = sanitized.strip('.:,;')
        
        # Remove extra punctuation
        sanitized = re.sub(r'[/()]', '', sanitized)
        
        # Limit filename length
        if len(sanitized) > 80:
            sanitized = sanitized[:80]
        
        # Capitalize each word
        sanitized = '_'.join(word.capitalize() for word in sanitized.split('_') if word)
        
        return sanitized or "Untitled"

    def _clean_separator_lines(self, content):
        """
        Removes lines containing only dashes (visual separators).
        """
        if not content:
            return ""
        
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if re.match(r'^\s*-{3,}\s*$', line):
                cleaned_lines.append("\n")
                continue
            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _merge_wrapped_lines(self, content):
        """
        Merges lines separated only for visual formatting.
        For laboratory reports, return content as-is to preserve test blocks.
        """
        return content

    def _is_unit(self, line):
        line_clean = line.strip().lower()
        known_units = {
            'g/dl', '%', 'fl', 'pg', 's', 'inr', 'mg/dl', 'ml/min', 'ratio', 'u/l',
            'meq/l', 'µg/dl', 'ug/dl', 'ng/ml', 'pg/ml', 'mg/l', 'x 10^3/µl', 'x 10^6/µl',
            'x 10^3/l', 'x 10^6/l'
        }
        if line_clean in known_units:
            return True
        if '10^' in line_clean:
            return True
        if '/' in line_clean and not any(char.isdigit() for char in line_clean):
            return True
        return False

    def _is_reference_range(self, line):
        # Matches patterns like 3,70 - 9,70 or 40 - or - 131 or 8 - 61
        return bool(re.match(r'^\s*\*?\s*(?:[0-9.,]+\s*-\s*[0-9.,]*|-\s*[0-9.,]+)\s*$', line))

    def _is_result(self, line):
        # Matches numbers with optional asterisk prefix, e.g. *2,83 or 4,23 or 81
        return bool(re.match(r'^\s*\*?\s*-?[0-9]+(?:,[0-9]+)?\s*$', line))

    def _parse_section_to_tests(self, section_name, text_content):
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # Filter out header matching the section name
        if lines and lines[0].upper() == section_name.upper():
            lines = lines[1:]
            
        tests = []
        current_test = {
            'name': None,
            'result': '',
            'unit': '',
            'reference': '',
            'observations': []
        }
        
        in_observation = False
        
        for line in lines:
            # Check observations
            if line.startswith('(Observaciones:') or in_observation:
                current_test['observations'].append(line)
                if line.endswith(')'):
                    in_observation = False
                else:
                    in_observation = True
            elif self._is_reference_range(line):
                current_test['reference'] = line
            elif self._is_unit(line):
                current_test['unit'] = line
            elif self._is_result(line):
                current_test['result'] = line
            else:
                # It's a test name candidate
                if current_test['name'] is not None:
                    # Save previous test if it has any data
                    if (current_test['result'] or current_test['unit'] or 
                        current_test['reference'] or current_test['observations']):
                        tests.append(current_test)
                    current_test = {
                        'name': line,
                        'result': '',
                        'unit': '',
                        'reference': '',
                        'observations': []
                    }
                else:
                    current_test['name'] = line
                    
        if current_test['name'] and (current_test['result'] or current_test['unit'] or 
                                     current_test['reference'] or current_test['observations']):
            tests.append(current_test)
            
        return tests

    def _format_tests(self, tests):
        formatted_blocks = []
        for test in tests:
            name = test['name'].lstrip('-').strip()
            result = test['result'].strip()
            unit = test['unit'].strip()
            
            # Combine reference and observations
            ref_parts = []
            if test['reference']:
                ref_parts.append(test['reference'].strip())
            if test['observations']:
                obs_str = " ".join(test['observations']).strip()
                ref_parts.append(obs_str)
            valores_referencia = " ".join(ref_parts)
            
            resultado_str = f"Resultado:{result}" if result.startswith('*') else f"Resultado: {result}"
            
            block = (
                f"Prueba: {name}\n"
                f"{resultado_str}\n"
                f"Unidad: {unit}\n"
                f"Valores Referencia: {valores_referencia}"
            )
            formatted_blocks.append(block)
            
        return "\n\n".join(formatted_blocks)

    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Generates Markdown content from extracted sections.
        """
        md_content = "# INFORME DE LABORATORIO\n\n"
        
        if case_id:
            md_content += f"**Número de Caso:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Archivo Origen:** {file_name}\n\n"
        
        md_content += "---\n\n"
        
        sections_data = [
            (self.hematologia_general, "Hematología General"),
            (self.hemostasia_fibrinolisis, "Hemostasia/Fibrinólisis"),
            (self.bioquimica_general, "Bioquímica General (Sangre)"),
            (self.proteinas_especificas, "Proteínas Específicas (Sangre)"),
            (self.vitaminas_sangre, "Vitaminas (Sangre)")
        ]
        
        for content, section_name in sections_data:
            if content and content.strip():
                md_content += f"## {section_name}\n\n"
                md_content += f"{content.strip()}\n\n"
                md_content += "---\n\n"
                
        return md_content