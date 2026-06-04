from preprocess.core.base_processor import BaseProcessor
import logging
from pathlib import Path
import re

class ProcessorErgoespirometria(BaseProcessor):
    """Specific processor for hospital ergoespirometria documents."""
    
    def __init__(self, file_path):
        """
        Initializes the ergoespirometria processor.
        
        Args:
            file_path (str): Path to the ergoespirometria PDF file
        """
        super().__init__(file_path)
        
        # Variables requested to store each section
        self.inicio = ""
        self.conclusiones = ""
        
    def __getattr__(self, name):
        """
        Dynamically returns section content when requested via legacy attributes.
        """
        # Avoid infinite recursion during initialization/attributes check
        if name in ['sections', 'args', 'file_path', 'text', 'structured_text', 'cleaned_structured_text', 'cleaned_text', 'inicio', 'conclusiones']:
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
        Cleans the text by removing the first title line, personal data, and the final signature.
        """
        if not self.text:
            return
            
        lines = self.text.split('\n')
        cleaned_lines = []
        start_collecting = False
        
        # Keywords that indicate a line contains personal data
        personal_data_keywords = [
            "nombre", "nhc", "dni", "sexo", "fecha", "edad", "apellidos", "cip", "nuss", 
            "historia clinica", "historia clínica", "procedencia", "médico", "medico", 
            "habitación", "habitacion", "servicio", "cama", "dirección", "direccion", 
            "teléfono", "telefono"
        ]
        
        for i, line in enumerate(lines):
            # Skip the first header line which usually contains "ERGOESPIROMETRÍA"
            if i == 0 and "ERGOESPIROMETR" in line.upper():
                continue
                
            # If we haven't started collecting, check if this line is part of personal data
            if not start_collecting:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                
                # Check for robust backup trigger
                if "Paciente bajo tratamiento" in line:
                    start_collecting = True
                else:
                    # Check if it has any personal data keywords
                    line_lower = stripped_line.lower()
                    is_personal = False
                    for kw in personal_data_keywords:
                        if kw in line_lower:
                            is_personal = True
                            break
                    
                    # If it doesn't contain personal data, start collecting
                    if not is_personal:
                        start_collecting = True
            
            # Stop collecting if we reach the signature line
            if ("Fdo" in line or "Firmado" in line) and "Colegiado" in line:
                break
                
            if start_collecting:
                cleaned_lines.append(line)
                
        self.cleaned_text = '\n'.join(cleaned_lines).strip()

    def _extract_sections(self):
        """
        Extracts specific sections dynamically based on bold, uppercase, and colon-terminated headers,
        stores them in variables, and saves them to text files.
        """
        if not hasattr(self, 'cleaned_text') or not self.cleaned_text:
            self._clean()
            
        text = getattr(self, 'cleaned_text', "")
        
        if not text:
            logging.warning("No text to extract sections from.")
            return {}
            
        # Find where conclusions starts
        conclusion_patterns = [
            r'(?mi)^conclusiones\s*:',
            r'(?mi)^conclusión\s*:',
            r'(?mi)^conclusion\s*:'
        ]
        
        conclusiones_start_idx = -1
        conclusion_header_text = "Conclusiones:"
        for pattern in conclusion_patterns:
            match = re.search(pattern, text)
            if match:
                conclusiones_start_idx = match.start()
                conclusion_header_text = match.group(0)
                break
                
        if conclusiones_start_idx == -1:
            for term in ["Conclusiones:", "CONCLUSIONES:", "Conclusión:", "CONCLUSIÓN:"]:
                idx = text.find(term)
                if idx != -1:
                    conclusiones_start_idx = idx
                    conclusion_header_text = term
                    break
                    
        search_text_range = text[:conclusiones_start_idx] if conclusiones_start_idx != -1 else text
        
        detected_headers = []
        
        # Method 1: Use style metadata from structured_text if available
        if hasattr(self, 'structured_text') and self.structured_text and "paginas" in self.structured_text:
            for pagina in self.structured_text["paginas"]:
                for linea in pagina["lineas"]:
                    texto = linea.get("texto_completo", "").strip()
                    if not texto:
                        continue
                    
                    if not texto.endswith(':'):
                        continue
                        
                    letters = [c for c in texto if c.isalpha()]
                    if not letters or not all(c.isupper() for c in letters):
                        continue
                        
                    content_name = texto[:-1].strip().lower()
                    if content_name in ["conclusiones", "conclusión", "conclusion"]:
                        continue
                        
                    is_bold = False
                    formato = linea.get("formato_principal", {})
                    if "bold" in formato.get("estilos", []):
                        is_bold = True
                    else:
                        for span in linea.get("spans_detallados", []):
                            if "bold" in span.get("estilos", []):
                                is_bold = True
                                break
                                
                    if is_bold:
                        if texto in search_text_range and texto not in detected_headers:
                            detected_headers.append(texto)
                            
        # Method 2: Fallback scanning cleaned text lines (for raw text / unit tests)
        if not detected_headers:
            lines = search_text_range.split('\n')
            for line in lines:
                texto = line.strip()
                if not texto:
                    continue
                    
                if not texto.endswith(':'):
                    continue
                    
                letters = [c for c in texto if c.isalpha()]
                if not letters or not all(c.isupper() for c in letters):
                    continue
                    
                content_name = texto[:-1].strip().lower()
                if content_name in ["conclusiones", "conclusión", "conclusion"]:
                    continue
                    
                if texto not in detected_headers:
                    detected_headers.append(texto)
                    
        sections = {}
        
        # Extract Inicio (everything before the first detected dynamic section)
        first_header_idx = text.find(detected_headers[0]) if detected_headers else -1
        if first_header_idx != -1:
            sections["inicio"] = text[:first_header_idx].strip()
        else:
            sections["inicio"] = text.strip()
            
        # Extract dynamic sections
        current_idx = 0
        for i, header in enumerate(detected_headers):
            start_idx = text.find(header, current_idx)
            if start_idx != -1:
                if i + 1 < len(detected_headers):
                    end_idx = text.find(detected_headers[i+1], start_idx + len(header))
                    if end_idx == -1:
                        end_idx = conclusiones_start_idx if conclusiones_start_idx != -1 else len(text)
                else:
                    end_idx = conclusiones_start_idx if conclusiones_start_idx != -1 else len(text)
                    
                section_key = header.replace(':', '').strip()
                sections[section_key] = text[start_idx:end_idx].strip()
                current_idx = end_idx
                
        # Extract Conclusions
        if conclusiones_start_idx != -1:
            conclusiones_content = text[conclusiones_start_idx:].strip()
            sections["Conclusiones"] = conclusiones_content
            clean_conclusion_header = conclusion_header_text.replace(':', '').strip()
            if clean_conclusion_header != "Conclusiones":
                sections[clean_conclusion_header] = conclusiones_content
        else:
            sections["Conclusiones"] = ""
            
        # Store in class variables for backward compatibility
        self.inicio = sections.get("inicio", "")
        self.conclusiones = sections.get("Conclusiones", "")
        
        # Save each section to a new text file
        try:
            output_dir = Path(self.file_path).parent / f"{Path(self.file_path).stem}_secciones"
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
            
        # Save in self.sections for compatibility with get_structured_text
        self.sections = []
        if self.inicio.strip():
            self.sections.append({
                'seccion': 'Inicio',
                'cuerpo': self.inicio,
                'nivel': 1,
                'subsecciones': []
            })
            
        for header in detected_headers:
            clean_name = header.replace(':', '').strip()
            content = sections.get(clean_name, "")
            if content.strip():
                self.sections.append({
                    'seccion': clean_name,
                    'cuerpo': content,
                    'nivel': 1,
                    'subsecciones': []
                })
                
        if self.conclusiones.strip():
            clean_conclusion_name = conclusion_header_text.replace(':', '').strip()
            self.sections.append({
                'seccion': clean_conclusion_name,
                'cuerpo': self.conclusiones,
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
        """
        if not content:
            return ""
        
        end_punctuation = {'.', '!', '?', ':', ';'}
        list_markers = ['-', '•', '*', '·']
        
        lines = content.split('\n')
        merged_lines = []
        current_line = ""
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                merged_lines.append("")
                continue
            
            is_list_item = any(stripped.startswith(marker) for marker in list_markers)
            is_numbered = len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)-'
            
            if is_list_item or is_numbered:
                if current_line:
                    merged_lines.append(current_line)
                current_line = stripped
                continue
            
            if current_line:
                last_char = current_line.rstrip()[-1] if current_line.rstrip() else ''
                
                if last_char in end_punctuation:
                    merged_lines.append(current_line)
                    current_line = stripped
                else:
                    current_line += " " + stripped
            else:
                current_line = stripped
        
        if current_line:
            merged_lines.append(current_line)
        
        return '\n'.join(merged_lines)

    def _generate_markdown_content(self, case_id=None, file_name=None):
        """
        Generates Markdown content from extracted sections.
        """
        md_content = "# INFORME DE ERGOESPIROMETRÍA\n\n"
        
        if case_id:
            md_content += f"**Número de Caso:** {case_id}\n\n"
        
        if file_name:
            md_content += f"**Archivo Origen:** {file_name}\n\n"
        
        md_content += "---\n\n"
        
        # Ensure sections are extracted
        if not hasattr(self, 'sections') or not self.sections:
            self._extract_sections()
            
        for section in self.sections:
            content = section['cuerpo']
            section_name = section['seccion']
            if content and content.strip():
                md_content += f"## {section_name}\n\n"
                md_content += f"{content.strip()}\n\n"
                md_content += "---\n\n"
                
        return md_content