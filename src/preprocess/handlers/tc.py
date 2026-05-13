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
            
            # 3. EL GRAN CORTE: Borrar desde el inicio hasta "Datos del Informe" (o "Datos Clínicos" si no hay Datos del Informe)
            # Esto ignora el nombre específico del hospital y los datos de paciente/peticionario
            patron_cabecera = r"^.*?(Datos del Informe|Datos Clínicos\s*/\s*Sospecha Diagnóstica)"
            texto = re.sub(patron_cabecera, r"\1", texto, flags=re.DOTALL | re.IGNORECASE)
            
            # 4. CORTE FINAL: Borrar desde "Estado del Informe:" hasta el final del documento.
            patron_pie = r"Estado del Informe:.*$"
            texto = re.sub(patron_pie, "", texto, flags=re.DOTALL | re.IGNORECASE)
            
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
            
            # Patrones para identificar el inicio de cada sección (soportando pérdida de tildes por OCR)
            secciones = {
                "datos_informe": r"Datos del Informe",
                "informe_principal": r"Informe Principal",
                "datos_clinicos": r"Datos Cl[íi]nicos\s*/\s*Sospecha Diagn[óo]stica",
                "exploraciones": r"Exploraciones Realizadas",
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
            contenido_secciones = {}
            for key, patron in secciones.items():
                match = re.search(patron, texto_seguro, flags=re.IGNORECASE)
                if match:
                    inicio = match.end()
                    
                    # Encontrar el fin de la sección actual (el inicio de la siguiente que esté después)
                    siguientes = [pos for k, pos in posiciones.items() if pos > match.start()]
                    fin = min(siguientes) if siguientes else len(texto_seguro)
                    
                    # Limpiar el contenido extraído
                    contenido = texto_seguro[inicio:fin].strip()
                    # Eliminar el guión inicial y saltos de línea extra si los hay al principio
                    if contenido.startswith('-'):
                        contenido = contenido[1:].strip()
                    contenido_secciones[key] = contenido
            
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
            
            # OBLIGATORIO: Guardar el resultado en self.args como una tupla
            self.args = (datos,)
            
        except Exception as e:
            logger.error(f"Error extrayendo secciones en ProcessorTC: {e}")
            # Si hay fallo crítico, instanciamos el modelo con el texto plano para no bloquear
            datos = InformeTC(texto_anonimizado=getattr(self, "cleaned_structured_text", ""))
            self.args = (datos,)

    def get_structured_text(self, output_dir=None):
        try:
            # Determina la ruta original de manera segura
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            
            # Determina dónde guardar el archivo
            if output_dir is None:
                output_dir = source_path.parent / f"{source_path.stem}_procesado"
            else:
                output_dir = Path(output_dir)
                
            output_dir.mkdir(parents=True, exist_ok=True)
            
            texto_final = getattr(self, "cleaned_structured_text", "")
            
            # Archivo de salida dinámico para evitar sobreescribir si están en la misma carpeta
            nombre_archivo = f"{source_path.stem}_Anonimizado.txt"
            ruta_archivo = output_dir / nombre_archivo
            
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                f.write(texto_final)
                
            return output_dir
            
        except Exception as e:
            logger.error(f"Error guardando el texto estructurado en ProcessorTC: {e}")
            return None
          
    def get_md(self, output_path=None, case_id=None):
        try:
            source_path = Path(getattr(self, 'file_path', 'informe_desconocido.pdf'))
            
            # Determinar la ruta de salida
            if output_path is None:
                output_path = source_path.parent / f"{source_path.stem}_informe.md"
            else:
                output_path = Path(output_path)
                
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            texto_final = getattr(self, "cleaned_structured_text", "")
            md_content = f"# Informe de Tomografía (TC)\n\n{texto_final}"
            
            # Guardar el archivo
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            return output_path
            
        except Exception as e:
            logger.error(f"Error generando el archivo Markdown en ProcessorTC: {e}")
            return None