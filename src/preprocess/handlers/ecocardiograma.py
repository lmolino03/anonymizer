from preprocess.core.base_processor import BaseProcessor
from models.ecocardiograma import HojaEcocardiograma
from utils.utils import clean_structured_text
import logging
import re
import json
from pathlib import Path


class ProcessorEcocardiograma(BaseProcessor):
    def __init__(self, file_path):
        super().__init__(file_path)

    def _parse_numeric_value(self, token):
        cleaned = str(token).strip().replace(",", ".")
        if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _clean(self):
        if not self.structured_text:
            logging.error(f"Structured text is empty for file: {self.file_path}")
            return

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
                "lineas": pagina["lineas"].copy(),
                "tablas": pagina.get("tablas", [])
            }
            cleaned_structured_text["paginas"].append(cleaned_page)

        self.structured_text = cleaned_structured_text

        all_lines = []
        for page_idx, pagina in enumerate(self.structured_text["paginas"]):
            for line_idx, linea in enumerate(pagina["lineas"]):
                all_lines.append({
                    "linea": linea,
                    "page_idx": page_idx,
                    "line_idx": line_idx,
                    "global_idx": len(all_lines),
                    "texto": linea.get("texto_completo", "").lower()
                })

        corte_idx = None
        for i, info in enumerate(all_lines):
            if "fecha procedimiento" in info["texto"]:
                corte_idx = i
                break

        if corte_idx is None:
            raise ValueError(f"No 'fecha procedimiento' found in {self.file_path}")

        global_counter = 0
        filtered_pages = []
        for pagina in self.structured_text["paginas"]:
            new_page = {
                "pagina": pagina["pagina"],
                "dimensiones": pagina["dimensiones"],
                "lineas": [],
                "tablas": pagina.get("tablas", [])
            }
            for linea in pagina["lineas"]:
                if global_counter >= corte_idx:
                    new_page["lineas"].append(linea)
                global_counter += 1
            if new_page["lineas"]:
                filtered_pages.append(new_page)

        self.structured_text["paginas"] = filtered_pages

        for pagina in self.structured_text["paginas"]:
            nuevas = []
            for linea in pagina["lineas"]:
                txt = linea.get("texto_completo", "").lower()
                if "firmado por" in txt or "realizado por" in txt:
                    break
                nuevas.append(linea)
            pagina["lineas"] = nuevas

        substrings_to_remove = [
            "Pág", "Page", "Pag", "http", "Fdo", "fdo", "Jaén", "NHC:", "DNI:", "NASS:",
            "Teléfono:", "Firmado", "Código de Informe:", "Informe Principal", "Nombre:",
            "Nº de Historia:", "F.Nacimiento:", "S.C.:", "Edad:", "BP ",
        ]

        cleaned_pages = []

        for pagina in self.structured_text["paginas"]:

            pagina_limpia, _ = clean_structured_text(
                {
                    "archivo": self.structured_text["archivo"],
                    "total_paginas": self.structured_text["total_paginas"],
                    "metadatos": self.structured_text["metadatos"],
                    "paginas": [pagina]
                },
                substrings_to_remove
            )

            pagina_limpia = pagina_limpia["paginas"][0]

            pagina_limpia["tablas"] = pagina["tablas"]

            cleaned_pages.append(pagina_limpia)

        self.cleaned_structured_text = {
            "archivo": self.structured_text["archivo"],
            "total_paginas": self.structured_text["total_paginas"],
            "metadatos": self.structured_text["metadatos"],
            "paginas": cleaned_pages
        }

        try:
            self.medidas_extraidas = self._extraer_medidas()
            logging.info("Medidas extraídas correctamente en _clean()")
        except Exception as e:
            logging.error(f"Error extrayendo medidas en _clean(): {e}")
            self.medidas_extraidas = {}

    def _normalizar_texto_medida(self, texto):
        texto = re.sub(r'\s+', ' ', texto or '').strip()
        texto = re.sub(r'(?<=[A-Za-zÁ-ÿÑñ])(?=\d)', ' ', texto)
        texto = re.sub(r'(?<=\d)(?=[A-Za-zÁ-ÿÑñ])', ' ', texto)
        texto = re.sub(r'(?<=[a-zá-ÿ])(?=[A-ZÁ-ÝÑ])', ' ', texto)
        return re.sub(r'\s+', ' ', texto).strip()

    def _extraer_medidas(self):
        paginas = self.cleaned_structured_text.get("paginas", [])
        if not paginas:
            return {}

        medidas_por_seccion = {}

        re_medida = re.compile(
            r"(?P<nombre>[A-Za-zÁ-ÿÑñ0-9_()/.',-]+(?:\s+[A-Za-zÁ-ÿÑñ0-9_()/.',-]+){0,6})\s+"
            r"(?P<valor>[-+]?\d+(?:[.,]\d+)?)(?:\s*(?P<unidad>mm|cm|cm²|ml|m/s|%|bpm|l/min|mmHg|m|s)(?:\s+(?:mm|cm|cm²|ml|m/s|%|bpm|l/min|mmHg|m|s))*)?",
            re.IGNORECASE,
        )

        def is_bold_arial(span):
            font = (span.get("fuente") or "").lower()
            estilos = set(span.get("estilos", []) or [])
            return ("arial" in font or "helvetica" in font) and "bold" in estilos

        stop_headers = {"ECOCARDIOGRAMA", "CONCLUSIONES", "HALLAZGOS", "RESULTADOS"}
        ignore_keys = {"nombre", "historia", "nacimiento", "s.c.", "edad", "bp", "sc", "fecha", "procedimiento"}

        active_column_headers = []

        for pagina in paginas:
            lineas = pagina.get("lineas", [])
            if not lineas:
                continue

            line_groups = []
            current_group = [lineas[0]]
            for i in range(1, len(lineas)):
                prev_y = current_group[-1]["posicion"]["y_superior"]
                curr_y = lineas[i]["posicion"]["y_superior"]
                if abs(curr_y - prev_y) < 8:
                    current_group.append(lineas[i])
                else:
                    line_groups.append(current_group)
                    current_group = [lineas[i]]
            line_groups.append(current_group)

            for group in line_groups:
                all_spans = []
                for l in group:
                    all_spans.extend(l.get("spans_detallados", []))
                
                new_headers_found = False
                for span in all_spans:
                    txt = span.get("texto", "").strip()
                    if not txt or any(k in txt.lower() for k in ignore_keys): continue
                    
                    if is_bold_arial(span) and not re.search(r'\d', txt):
                        header_txt = txt.rstrip(":").strip()
                        if any(header_txt.upper().startswith(h) for h in stop_headers):
                            return medidas_por_seccion
                        
                        new_h = {"texto": header_txt, "x0": span["posicion"]["x0"], "x1": span["posicion"]["x1"]}
                        
                        updated = False
                        for h in active_column_headers:
                            if abs(h["x0"] - new_h["x0"]) < 45:
                                h.update(new_h)
                                updated = True
                                break
                        if not updated:
                            active_column_headers.append(new_h)
                        new_headers_found = True

                if new_headers_found:
                    active_column_headers.sort(key=lambda x: x["x0"])

                buckets = {}
                default_title = "Medidas"
                
                for span in all_spans:
                    txt = span.get("texto", "").strip()
                    if not txt: continue
                    if is_bold_arial(span) and not re.search(r'\d', txt): continue
                    
                    x_mid = (span["posicion"]["x0"] + span["posicion"]["x1"]) / 2
                    assigned_title = default_title
                    
                    if active_column_headers:
                        headers = sorted(active_column_headers, key=lambda x: x["x0"])
                        fronteras = []
                        for i in range(len(headers) - 1):
                            mid_point = (headers[i]["x1"] + headers[i+1]["x0"]) / 2
                            fronteras.append(mid_point)
                        
                        idx = 0
                        found = False
                        for b in fronteras:
                            if x_mid < b:
                                assigned_title = headers[idx]["texto"]
                                found = True
                                break
                            idx += 1
                        
                        if not found:
                            assigned_title = headers[-1]["texto"]
                            
                        if x_mid < headers[0]["x0"] - 60:
                            assigned_title = default_title
                    
                    buckets.setdefault(assigned_title, []).append(span)

                for title, bucket_spans in buckets.items():
                    bucket_spans.sort(key=lambda s: s["posicion"]["x0"])
                    bucket_text = " ".join(s.get("texto", "") for s in bucket_spans)
                    txt_norm = self._normalizar_texto_medida(bucket_text)
                    
                    for match in re_medida.finditer(txt_norm):
                        nombre = match.group("nombre").strip(" -:;,.()")
                        v_str = match.group("valor")
                        valor = self._parse_numeric_value(v_str)
                        unidad = (match.group("unidad") or "").strip()

                        if not nombre or valor is None: continue
                        if any(k in nombre.lower() for k in ignore_keys): continue

                        x_pos = bucket_spans[0]["posicion"]["x0"]
                        for s in bucket_spans:
                            s_t = s.get("texto", "")
                            if v_str in s_t or v_str.replace(".", ",") in s_t:
                                x_pos = s["posicion"]["x0"]
                                break
                        
                        medidas_por_seccion.setdefault(title, []).append({
                            "nombre": nombre,
                            "valor": valor,
                            "unidad": unidad,
                            "posicion_x": round(x_pos, 2),
                            "posicion_y": round(group[0]["posicion"]["y_superior"], 2),
                        })

        return medidas_por_seccion

    def _extract_sections(self):
        if not hasattr(self, 'cleaned_structured_text') or not self.cleaned_structured_text:
            logging.warning(f"No clean text available in {self.file_path}")
            return []

        def es_titulo(linea):
            texto = linea.get("texto_completo", "").strip()
            if not texto:
                return False

            texto_normalizado = re.sub(r'\s+', ' ', texto).strip().upper()
            if texto_normalizado in {"ECOCARDIOGRAMA", "CONCLUSIONES", "HALLAZGOS", "RESULTADOS"}:
                return True

            if texto_normalizado.startswith("ECOCARDIOGRAMA") or texto_normalizado.startswith("CONCLUSIONES"):
                return True

            return False

        all_lines = []
        for pagina in self.cleaned_structured_text["paginas"]:
            for linea in pagina["lineas"]:
                all_lines.append(linea)

        sections = []
        current_section = None
        current_body = []

        def guardar_seccion():
            nonlocal current_section, current_body
            if current_section is not None:
                current_section["cuerpo"] = "\n".join(current_body).strip()
                sections.append(current_section)
                current_section = None
                current_body = []

        for linea in all_lines:
            texto = linea.get("texto_completo", "").strip()
            if not texto:
                continue
            if es_titulo(linea):
                guardar_seccion()
                current_section = {"seccion": texto, "cuerpo": ""}
                current_body = []
                continue
            if current_section is not None:
                current_body.append(texto)

        guardar_seccion()

        self.sections = sections
        logging.info(f"Extracted {len(sections)} sections automatically")
        self._convertir_secciones_a_args()
        return sections

    def _convertir_secciones_a_args(self):
        fecha_procedimiento = None

        for pagina in self.cleaned_structured_text["paginas"]:
            for linea in pagina["lineas"]:
                texto = linea.get("texto_completo", "")
                if "fecha procedimiento" in texto.lower():
                    partes = texto.split(":")
                    fecha_procedimiento = partes[-1].strip() if len(partes) > 1 else texto.strip()
                    break
            if fecha_procedimiento:
                break

        found = {}
        for index, section in enumerate(self.sections):
            name = section.get("seccion", "").lower().strip()
            content = (section.get("cuerpo") or "").strip()
            if not content:
                continue

            if "concl" in name or "concl" in content.lower():
                found["conclusiones"] = content
            elif "eco" in name or "cardio" in name or index == 0:
                found["ecocardiograma"] = content

        ecocardiograma = found.get("ecocardiograma")
        conclusiones = found.get("conclusiones")

        self.args = (
            fecha_procedimiento, self.medidas_extraidas, ecocardiograma, conclusiones
        )

        encontradas = sum(1 for x in self.args if x is not None)
        logging.info(f"Args assembled: {encontradas}/4 found")

    def _validate_result(self):
        super()._validate_result()
        if not hasattr(self, 'args'):
            logging.warning("No args extracted")
            return
        _, _, ecocardiograma, conclusiones = self.args
        if ecocardiograma is None:
            logging.warning(f"WARNING: 'ECOCARDIOGRAMA' not found in {self.file_path}")
        if conclusiones is None:
            logging.warning(f"WARNING: 'CONCLUSIONES' not found in {self.file_path}")

    def get_md(self, output_path=None, case_id=None):
        logging.info(f"get_md called, has_args={hasattr(self, 'args')}")
        try:
            if not hasattr(self, 'args'):
                self._extract_sections()

            if output_path is None:
                source_path = Path(self.file_path)
                output_path = source_path.parent / f"{source_path.stem}_ecocardiograma.md"
            else:
                output_path = Path(output_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            file_name = Path(self.file_path).name
            md_content = self._generate_markdown_content(case_id, file_name)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            logging.info(f"MD generated: {output_path}")
            return output_path

        except Exception as e:
            logging.error(f"Error generating MD for {self.file_path}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None

    def _generate_markdown_content(self, case_id=None, file_name=None):
        fecha_procedimiento, medidas, ecocardiograma, conclusiones = self.args

        md = "# ECOCARDIOGRAMA SHEET\n\n"
        if case_id:
            md += f"**Case Number:** {case_id}  \n"
        if file_name:
            md += f"**File Name:** {file_name}  \n"
        if fecha_procedimiento:
            md += f"**Procedure Date:** {fecha_procedimiento}  \n"
        md += "\n---\n\n"

        if medidas:
            md += "## Medidas\n\n"
            for titulo, items in medidas.items():
                md += f"### {titulo}\n\n"
                for item in items:
                    nombre = item.get("nombre", "")
                    valor = item.get("valor")
                    unidad = item.get("unidad", "")
                    md += f"- {nombre}: {valor} {unidad}\n"
                md += "\n"

        for section in getattr(self, "sections", []) or []:
            title = section.get("seccion", "Sección").strip()
            content = (section.get("cuerpo") or "").strip()
            if title and content:
                md += f"## {title}\n\n{content}\n\n"

        if ecocardiograma and ecocardiograma.strip() and ecocardiograma.strip() != "None":
            md += f"## Hallazgos\n\n{ecocardiograma.strip()}\n\n"

        if conclusiones and conclusiones.strip() and conclusiones.strip() != "None":
            md += f"## Conclusiones\n\n{conclusiones.strip()}\n\n"

        md += "---\n\n*Report generated automatically*\n"
        return md

    def get_structured_text(self, output_dir=None):
        try:
            if not hasattr(self, 'sections'):
                self._extract_sections()

            if output_dir is None:
                source_path = Path(self.file_path)
                output_dir = source_path.parent / f"{source_path.stem}_structured"
            else:
                output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            fecha_procedimiento, _, _, _ = self.args

            if fecha_procedimiento:
                with open(output_dir / "Fecha_Procedimiento.txt", 'w', encoding='utf-8') as f:
                    f.write(fecha_procedimiento)

            medidas_carpeta = output_dir / "Medidas"
            medidas_carpeta.mkdir(exist_ok=True)
            logging.info("Created Medidas folder")

            for section in self.sections:
                titulo = section.get("seccion", "").strip().upper()
                cuerpo = section.get("cuerpo", "").strip()
                if not cuerpo:
                    continue
                if not any(token in titulo for token in ("ECOCARDIOGRAMA", "CONCLUSIONES", "HALLAZGOS", "RESULTADOS")):
                    continue
                file_name = re.sub(r'[<>:"/\\|?*\s]+', '_', section["seccion"])
                file_name = file_name.strip('._')[:80] or "Sin_titulo"
                with open(output_dir / f"{file_name}.txt", 'w', encoding='utf-8') as f:
                    f.write(cuerpo)
                logging.info(f"Created: {file_name}.txt")

            medidas = self._extraer_medidas()
            medidas_json_path = medidas_carpeta / "medidas.json"

            with open(medidas_json_path, "w", encoding="utf-8") as f:
                json.dump({"medidas": medidas}, f, indent=4, ensure_ascii=False)

            logging.info(f"Archivo de medidas generado: {medidas_json_path}")


            logging.info(f"Archivo de medidas generado: {medidas_json_path}")
            logging.info(f"Structured text generated at: {output_dir}")
            return output_dir

        except Exception as e:
            logging.error(f"Error generating structured text: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
