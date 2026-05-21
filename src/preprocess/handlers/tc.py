import logging
import re
from pathlib import Path
from preprocess.core.base_processor import BaseProcessor
from models.tc import InformeTC

logger = logging.getLogger(__name__)

class ProcessorTC(BaseProcessor):
    
    def _clean(self):
        """
        Limpia el texto bruto eliminando la cabecera, los datos personales del paciente,
        del peticionario y el estado final del informe.
        """
        if not hasattr(self, 'text') or not self.text:
            self.cleaned_structured_text = ""
            logger.warning("El texto de entrada está vacío o es nulo en ProcessorTC.")
            return

        texto = self.text
        
        try:
            # 1. Borrar los "Page X of Y" (ignorando mayúsculas/minúsculas)
            texto = re.sub(r"Page \d+ of \d+\n", "", texto, flags=re.IGNORECASE)
            
            # 2. Eliminar el pie de página (la URL rara de emdae... y la fecha de impresión)
            texto = re.sub(r"http://emdae[^\n]+\n", "", texto, flags=re.IGNORECASE)
            
            # Borrar desde el inicio hasta "Datos del Informe"
            # Esto ignora el nombre específico del hospital y los datos de paciente/peticionario
            patron_cabecera = r"^.*?(Datos del Informe|Datos Clínicos\s*/\s*Sospecha Diagnóstica)"
            texto = re.sub(patron_cabecera, r"\1", texto, flags=re.DOTALL | re.IGNORECASE)
            
            # Borrar desde "Estado del Informe:" hasta el final del documento.
            patron_pie = r"Estado del Informe:.*$"
            texto = re.sub(patron_pie, "", texto, flags=re.DOTALL | re.IGNORECASE)
            
            # Eliminar el Código de Informe
            texto = re.sub(r"Código de Informe:.*?\n", "", texto, flags=re.IGNORECASE)
            
            # Guardamos el texto resultante limpio
            self.cleaned_structured_text = texto.strip()
            
        except Exception as e:
            logger.error(f"Error al aplicar las expresiones regulares en ProcessorTC: {e}")
            # Guardamos el texto aunque haya fallado algún regex, para no dejar el programa bloqueado
            self.cleaned_structured_text = texto.strip()
        
    def _extract_sections(self):
        """
        Extrae las diferentes secciones del texto limpio y las guarda en variables.
        """
        try:
            texto_seguro = getattr(self, "cleaned_structured_text", "")
            
            # Patrones EXACTOS para tu estructura
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
                    
                    # Limpiar el contenido extraído (sin borrar guiones)
                    contenido = texto_seguro[inicio:fin].strip()
                    contenido_secciones[key] = contenido
            
            if "hallazgos" in contenido_secciones:
                texto_hallazgos = contenido_secciones["hallazgos"]
                
                # Buscamos la tabla desubicada
                patron_tabla = r"(Fecha\s+Exploraci[óo]n\s+C[óo]digo.*)"
                match_tabla = re.search(patron_tabla, texto_hallazgos, flags=re.IGNORECASE | re.DOTALL)
                
                if match_tabla:
                    tabla_texto = match_tabla.group(1).strip()
                    # 1. Recortamos la tabla de los hallazgos
                    contenido_secciones["hallazgos"] = texto_hallazgos[:match_tabla.start()].strip()
                    
                    # 2. Reconstruimos la tabla como texto plano limpio
                    lineas = [linea.strip() for linea in tabla_texto.split('\n') if linea.strip()]
                    
                    # Comprobamos que tenemos al menos las cabeceras y una fila de datos (5 líneas)
                    if len(lineas) >= 5 and "Fecha" in lineas[0]:
                        # Unimos las cabeceras separadas por unos cuantos espacios
                        cabecera = f"{lineas[0]}    {lineas[1]}    {lineas[2]}"
                        
                        # Unimos la fecha correcta (línea 3) y la exploración (línea 4)
                        # Ignoramos intencionadamente la línea 5 (la fecha extra que sobra)
                        datos = f"{lineas[3]}    {lineas[4]}"
                        
                        # Lo guardamos todo junto, limpio y estructurado
                        contenido_secciones["exploraciones"] = f"{cabecera}\n{datos}"
                    else:
                        # Si el formato es distinto, lo dejamos como estaba por seguridad
                        contenido_secciones["exploraciones"] = tabla_texto
            
            # Guardamos el diccionario para que get_structured_text cree los ficheros
            self.secciones_diccionario = contenido_secciones

            # Guardamos en el modelo de datos
            datos = InformeTC(
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
            logger.error(f"Error extrayendo secciones en ProcessorTC: {e}")
            datos = InformeTC(texto_anonimizado=getattr(self, "cleaned_structured_text", ""))
            self.args = (datos,)

    def get_structured_text(self, output_dir=None):
        try:
            # Determina la ruta original de manera segura
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            
            # Determina dónde guardar los archivos
            if output_dir is None:
                output_dir = source_path.parent / f"{source_path.stem}_procesado"
            else:
                output_dir = Path(output_dir)
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Recuperamos el diccionario de secciones que guardamos antes
            secciones = getattr(self, "secciones_diccionario", {})
            
            # Creamos un archivo por cada sección (tenga contenido o esté vacía)
            for nombre_seccion, contenido in secciones.items():
                nombre_archivo = f"{nombre_seccion}.txt"
                ruta_archivo = output_dir / nombre_archivo
                
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.write(contenido.strip())
                
            return output_dir
            
        except Exception as e:
            logger.error(f"Error guardando el texto estructurado en ProcessorTC: {e}")
            return None
          
    def get_md(self, output_path=None, case_id=None):
        try:
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            
            # Determinar la ruta de salida
            if output_path is None:
                output_dir = source_path.parent / f"{source_path.stem}_informe_md"
            else:
                # En lugar de un solo archivo, creamos una carpeta "markdown" dentro del reporte
                output_dir = Path(output_path).parent / "markdown"
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            secciones = getattr(self, "secciones_diccionario", {})
            
            for nombre_seccion, contenido in secciones.items():
                nombre_archivo = f"{nombre_seccion}.md"
                ruta_archivo = output_dir / nombre_archivo
                
                titulo = nombre_seccion.replace("_", " ").title()
                md_content = f"# {titulo}\n\n{contenido.strip()}"
                
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
            return output_dir
            
        except Exception as e:
            logger.error(f"Error generando los archivos Markdown en ProcessorTC: {e}")
            return None