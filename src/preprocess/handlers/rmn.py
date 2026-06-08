import logging
from pathlib import Path
import re

from preprocess.core.base_processor import BaseProcessor
from preprocess.readers.pdf_reader import PDFReader
from models.rmn import InformeRMN

logger = logging.getLogger(__name__)

class ProcessorRMN(BaseProcessor):
    """Procesador específico para informes de RMN."""
    
    def _clean(self):
        """
        Extrae el texto limpiando los datos de la plantilla médica (cabeceras, paciente, etc.)
        """
        try:
            texto = PDFReader.extract_only_text(self.file_path, include_tables=False, clean_medical_report=True)
            
            # Limpiar pies de página específicos si quedan
            texto = re.sub(r"Código de Informe:.*?\n", "", texto, flags=re.IGNORECASE)
            
            # Limpiar firmas (fdo)
            texto = re.sub(r"(?im)^fdo[\.,]?\s+.*$\n?", "", texto)
            
            # Guardamos el texto resultante limpio
            self.cleaned_structured_text = texto.strip()
            
        except Exception as e:
            logger.error(f"Error al aplicar las expresiones regulares en ProcessorRMN: {e}")
            # Guardamos el texto aunque haya fallado algún regex
            if not hasattr(self, "cleaned_structured_text"):
                self.cleaned_structured_text = ""
        
    def _extract_sections(self):
        """
        Extrae las diferentes secciones del texto limpio y las guarda en variables.
        """
        try:
            texto_seguro = getattr(self, "cleaned_structured_text", "")
            
            # Patrones EXACTOS para la estructura
            secciones = {
                "datos_informe": r"Datos del Informe",
                "informe_principal": r"Informe Principal",
                "datos_clinicos": r"Datos Cl[íi]nicos\s*/\s*Sospecha Diagn[óo]stica",
                "exploraciones": r"Exploraciones\s+Realizadas",
                "anatomias": r"Anatom[íi]as Estudiadas",
                "hallazgos": r"Hallazgos",
                "indicacion": r"Indicaci[óo]n diagn[óo]stica",
                "recomendaciones": r"Recomendaciones"
            }
            
            # Encontrar las posiciones de inicio de cada sección
            posiciones = {}
            for key, patron in secciones.items():
                match = re.search(patron, texto_seguro, flags=re.IGNORECASE)
                if match:
                    posiciones[key] = match.start()
                    
            # Extraer el contenido de cada sección
            contenido_secciones = {k: "" for k in secciones.keys()}
            for key, patron in secciones.items():
                match = re.search(patron, texto_seguro, flags=re.IGNORECASE)
                if match:
                    inicio = match.end()
                    
                    # Encontrar el fin de la sección actual buscando la siguiente más cercana
                    siguientes = [pos for k, pos in posiciones.items() if pos > match.start()]
                    fin = min(siguientes) if siguientes else len(texto_seguro)
                    
                    # Limpiar el contenido extraído
                    contenido = texto_seguro[inicio:fin].strip()
                    contenido_secciones[key] = contenido
            
            # Limpiar 'Código' de exploraciones
            if "exploraciones" in contenido_secciones:
                contenido_secciones["exploraciones"] = contenido_secciones["exploraciones"].replace("Código", "").replace("Codigo", "").strip()
                contenido_secciones["exploraciones"] = re.sub(r"^[ \t]*\n", "", contenido_secciones["exploraciones"], flags=re.MULTILINE)
                contenido_secciones["exploraciones"] = re.sub(r"\n{3,}", "\n\n", contenido_secciones["exploraciones"])

            # Añadir el contenido de TODAS las secciones a 'datos_informe'
            texto_todas_secciones = []
            if contenido_secciones.get("datos_informe", "").strip():
                texto_todas_secciones.append(contenido_secciones["datos_informe"].strip())
                
            for k, v in contenido_secciones.items():
                if k != "datos_informe" and v.strip():
                    titulo = k.replace('_', ' ').title()
                    texto_todas_secciones.append(f"--- {titulo} ---\n{v.strip()}")
                    
            contenido_secciones["datos_informe"] = "\n\n".join(texto_todas_secciones)
            
            # Guardamos el diccionario para que get_structured_text cree los ficheros
            self.secciones_diccionario = contenido_secciones

            # Guardamos en el modelo de datos
            datos = InformeRMN(
                texto_anonimizado=texto_seguro,
                datos_informe=contenido_secciones.get("datos_informe", ""),
                informe_principal=contenido_secciones.get("informe_principal", ""),
                datos_clinicos=contenido_secciones.get("datos_clinicos", ""),
                exploraciones=contenido_secciones.get("exploraciones", ""),
                anatomias=contenido_secciones.get("anatomias", ""),
                hallazgos=contenido_secciones.get("hallazgos", ""),
                indicacion=contenido_secciones.get("indicacion", ""),
                recomendaciones=contenido_secciones.get("recomendaciones", "")
            )
            
            self.args = (datos,)
            
        except Exception as e:
            logger.error(f"Error extrayendo secciones en ProcessorRMN: {e}")
            datos = InformeRMN(texto_anonimizado=getattr(self, "cleaned_structured_text", ""))
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
            for nombre_seccion, contenido in secciones.items():
                contenido_limpio = contenido.strip()
                
                # Si la sección tiene 1 carácter o menos (ej. un guion suelto), se vacía
                if len(contenido_limpio) <= 1:
                    contenido_limpio = ""
                
                if "explorac" in nombre_seccion.lower():
                    datos_json = self._parsear_exploraciones_a_json(contenido_limpio)
                    if datos_json:
                        json_file = output_dir / f"{nombre_seccion}.json"
                        with open(json_file, 'w', encoding='utf-8') as f:
                            json.dump(datos_json, f, ensure_ascii=False, indent=4)
                        continue

                nombre_archivo = f"{nombre_seccion}.txt"
                ruta_archivo = output_dir / nombre_archivo
                
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.write(contenido_limpio)
                
            return output_dir
            
        except Exception as e:
            logger.error(f"Error guardando el texto estructurado en ProcessorRMN: {e}")
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
                
                # Si la sección tiene 1 carácter o menos (ej. un guion suelto), se vacía
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
            logger.error(f"Error generando los archivos Markdown en ProcessorRMN: {e}")
            return None
