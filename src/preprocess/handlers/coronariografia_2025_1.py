import logging
from pathlib import Path
import re

from preprocess.core.base_processor import BaseProcessor
from preprocess.readers.pdf_reader import PDFReader
from models.coronariografia_2025_1 import InformeCoronariografia2025_1

logger = logging.getLogger(__name__)

class ProcessorCoronariografia2025_1(BaseProcessor):
    """Procesador específico para informes de Coronariografía (formato 2025_1)."""
    
    def _clean(self):
        try:
            # En 2025_1 necesitamos las tablas (Solicitud, Datos Antropométricos, Acceso Vascular)
            texto = PDFReader.extract_only_text(self.file_path, include_tables=True)
            texto = re.sub(r"(?im)^fdo[\.,]?\s+.*$\n?", "", texto)
            
            # Limpiar firmas de médicos (Ej: nombre en una línea y "Facultativo Especialista de Área" en la siguiente)
            texto = re.sub(r"(?im)^[^\n]{1,60}\n\s*(?:Facultativo Especialista de Área|F\.E\.A\.).*$\n?", "", texto)
            # Limpiar la línea si la titulación está en la misma línea
            texto = re.sub(r"(?im)^.*?(?:Facultativo Especialista de Área|F\.E\.A\.).*$\n?", "", texto)
            
            # Limpiar cabeceras y pies de página
            texto = re.sub(r"(?im)^\s*https?://.*$", "", texto)
            texto = re.sub(r"(?im)^\s*---\s*PAGE\s+\d+\s*---\s*$", "", texto)
            texto = re.sub(r"(?im)^\s*Page\s+\d+\s+of\s+\d+\s*$", "", texto)
            texto = re.sub(r"(?im)^\s*Página\s+\d+\s+de\s+\d+\s*$", "", texto)
            texto = re.sub(r"(?im)^.*\(?NHC:\s*\d+\)?.*?Página\s+\d+\s+de\s+\d+.*$\n?", "", texto)
            texto = re.sub(r"(?im)^\s*Informe generado el.*$\n?", "", texto)
            
            self.cleaned_structured_text = texto.strip()
            
        except Exception as e:
            logger.error(f"Error al limpiar texto en ProcessorCoronariografia2025_1: {e}")
            if not hasattr(self, "cleaned_structured_text"):
                self.cleaned_structured_text = ""
        
    def _extract_sections(self):
        try:
            texto_seguro = getattr(self, "cleaned_structured_text", "")
            
            secciones = {
                "solicitud": r"Solicitud",
                "datos_antropometricos": r"Datos Antropométricos",
                "historia_clinica": r"Historia Clínica actual:?",
                "analitica": r"Analítica:",
                "acceso_vascular": r"Acceso Vascular",
                "informacion_post_proceso": r"Información Post-Proceso",
                "resumen_hallazgos": r"Resumen de hallazgos en el Diagnóstico",
                "ventriculografia_izquierda": r"Ventriculografía Izquierda",
                "lesiones_coronarias": r"Lesiones Coronarias \(Identificación, Evaluación y Tratamiento\)",
                "tratamiento_post_proceso": r"Tratamiento Post-Proceso \(medidas generales y medicación\)"
            }
            
            posiciones = {}
            for key, patron in secciones.items():
                match = re.search(patron, texto_seguro, flags=re.IGNORECASE)
                if match:
                    posiciones[key] = match.start()
                    
            contenido_secciones = {k: "" for k in secciones.keys()}
            for key, patron in secciones.items():
                match = re.search(patron, texto_seguro, flags=re.IGNORECASE)
                if match:
                    inicio = match.end()
                    siguientes = [pos for k, pos in posiciones.items() if pos > match.start()]
                    fin = min(siguientes) if siguientes else len(texto_seguro)
                    contenido = texto_seguro[inicio:fin].strip()
                    contenido_secciones[key] = contenido
                    
            # Combinar ventriculografia y lesiones en resumen_hallazgos
            resumen_text = contenido_secciones.get("resumen_hallazgos", "").strip()
            ventriculo_text = contenido_secciones.pop("ventriculografia_izquierda", "").strip()
            lesiones_text = contenido_secciones.pop("lesiones_coronarias", "").strip()
            
            partes = []
            if resumen_text:
                partes.append(resumen_text)
            if ventriculo_text:
                partes.append(f"Ventriculografía Izquierda:\n{ventriculo_text}")
            if lesiones_text:
                partes.append(f"Lesiones Coronarias:\n{lesiones_text}")
                
            contenido_secciones["resumen_hallazgos"] = "\n\n".join(partes)
            
            self.secciones_diccionario = contenido_secciones

            datos = InformeCoronariografia2025_1(
                texto_anonimizado=texto_seguro,
                solicitud=contenido_secciones.get("solicitud", ""),
                datos_antropometricos=contenido_secciones.get("datos_antropometricos", ""),
                historia_clinica=contenido_secciones.get("historia_clinica", ""),
                analitica=contenido_secciones.get("analitica", ""),
                acceso_vascular=contenido_secciones.get("acceso_vascular", ""),
                informacion_post_proceso=contenido_secciones.get("informacion_post_proceso", ""),
                resumen_hallazgos=contenido_secciones.get("resumen_hallazgos", ""),
                ventriculografia_izquierda="",
                lesiones_coronarias="",
                tratamiento_post_proceso=contenido_secciones.get("tratamiento_post_proceso", "")
            )
            
            self.args = (datos,)
            
        except Exception as e:
            logger.error(f"Error extrayendo secciones en ProcessorCoronariografia2025_1: {e}")
            datos = InformeCoronariografia2025_1(texto_anonimizado=getattr(self, "cleaned_structured_text", ""))
            self.args = (datos,)

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
        try:
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            if output_dir is None:
                output_dir = source_path.parent / f"{source_path.stem}_procesado"
            else:
                output_dir = Path(output_dir)
                
            output_dir.mkdir(parents=True, exist_ok=True)
            secciones = getattr(self, "secciones_diccionario", {})
            
            import json
            
            # Guardar JSON único con todas las tablas detectadas y sus coordenadas
            tables_data = self.get_tables_json_data()
            if tables_data:
                tables_json_file = output_dir / "tablas_detectadas.json"
                with open(tables_json_file, 'w', encoding='utf-8') as f:
                    json.dump(tables_data, f, ensure_ascii=False, indent=4)
                    
            for nombre_seccion, contenido in secciones.items():
                contenido_limpio = contenido.strip()
                if len(contenido_limpio) <= 1:
                    contenido_limpio = ""
                
                # Removed custom _parsear_exploraciones_a_json logic as per request.
                
                nombre_archivo = f"{nombre_seccion}.txt"
                ruta_archivo = output_dir / nombre_archivo
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.write(contenido_limpio)
                
            return output_dir
        except Exception as e:
            logger.error(f"Error guardando el texto estructurado: {e}")
            return None
          
    def get_md(self, output_path=None, case_id=None):
        try:
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            if output_path is None:
                output_dir = source_path.parent / f"{source_path.stem}_informe_md"
            else:
                output_dir = Path(output_path).parent / "markdown"
                
            output_dir.mkdir(parents=True, exist_ok=True)
            secciones = getattr(self, "secciones_diccionario", {})
            
            for nombre_seccion, contenido in secciones.items():
                contenido_limpio = contenido.strip()
                if len(contenido_limpio) <= 1:
                    contenido_limpio = ""

                nombre_archivo = f"{nombre_seccion}.md"
                ruta_archivo = output_dir / nombre_archivo
                
                titulo = nombre_seccion.replace("_", " ").title()
                md_content = f"# {titulo}\n\n{contenido_limpio}"
                
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
            return output_dir
        except Exception as e:
            logger.error(f"Error generando archivos Markdown: {e}")
            return None
