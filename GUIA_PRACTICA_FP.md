# Guía de Prácticas: Añadir un Nuevo Tipo de Documento

¡Hola! Esta guía está diseñada para ayudarte a entender cómo extender el sistema de anonimización de informes médicos. Sigue estos pasos para añadir un nuevo tipo de documento (por ejemplo, "Radiología" o "Receta").

---

## Introducción: ¿Cómo funciona el código?
El proyecto está organizado de forma modular. Para añadir un nuevo tipo de documento, no tenemos que cambiar todo el programa, solo añadir piezas en lugares específicos:

1.  **Modelo (`src/models/`)**: Define *qué* datos queremos guardar.
2.  **Handler (`src/preprocess/handlers/`)**: Es el "cerebro" que lee el PDF y extrae los datos.
3.  **Factoría (`src/preprocess/core/factory.py`)**: Es el "conserje" que decide qué cerebro usar según el tipo de documento.
4.  **Interfaz (`src/gui/main_window.py`)**: Es la cara visible donde el usuario elige el documento.

---

## Paso 1: Definir el "Molde" (Modelo de Datos)
Primero, necesitamos una clase que diga qué información vamos a sacar del PDF.

Crea un archivo nuevo: `src/models/mi_documento.py`
```python
from dataclasses import dataclass

@dataclass
class MiDocumento:
    # Define aquí los campos que vas a extraer
    fecha: str
    diagnostico: str
    medico: str
```

**¡No olvides registrarlo!** Abre `src/models/__init__.py` y añade:
```python
from .mi_documento import MiDocumento
```

---

## Paso 2: Crear el Procesador (Handler)
Aquí es donde ocurre la "magia". Tienes que heredar de `BaseProcessor` y rellenar dos funciones obligatorias.

Crea un archivo nuevo: `src/preprocess/handlers/mi_documento.py`
```python
from preprocess.core.base_processor import BaseProcessor
from models.mi_documento import MiDocumento

class ProcessorMiDocumento(BaseProcessor):
    def _clean(self):
        """
        Aquí limpias el texto. Por ahora, puedes simplemente
        copiar lo que hay en structured_text.
        """
        self.cleaned_structured_text = self.structured_text
        
    def _extract_sections(self):
        """
        Aquí buscas los datos en el texto y creas el objeto.
        """
        # Ejemplo rápido de extracción manual
        datos = MiDocumento(
            fecha="01/01/2024", 
            diagnostico="Ejemplo de prueba",
            medico="Dr. García"
        )
        
        # OBLIGATORIO: Guardar el resultado en self.args como una tupla
        self.args = (datos,) 
```

---

## Paso 3: Registrar en la Factoría
Ahora tenemos que decirle al programa que este nuevo procesador existe.

Abre `src/preprocess/core/factory.py`:
```python
# 1. Importa tu nuevo procesador al principio
from preprocess.handlers.mi_documento import ProcessorMiDocumento

class ProcessorFactory:
    @staticmethod
    def create_processor(file_path, document_type):
        processors = {
            'alta': ProcessorAlta,
            'evolucion': ProcessorEvolucion,
            'anamnesis': ProcessorAnamnesis,
            'mi_doc': ProcessorMiDocumento # 2. Añade tu clave y el nombre de la clase
        }
        # ...
```

---

## Paso 4: Añadir el botón a la Aplicación
Para que el usuario pueda elegir tu nuevo documento, añádelo a la lista de la interfaz.

Abre `src/gui/main_window.py` y busca donde dice `types = [...]` dentro de `init_ui`:
```python
types = [
    ("Informe de Alta", "alta"), 
    ("Anamnesis", "anamnesis"), 
    ("Evolución", "evolucion"),
    ("Mi Nuevo Doc", "mi_doc") # <- La clave "mi_doc" debe coincidir con la de la Factoría
]
```

---

## 🚀 Paso 5: ¡A probar!
1. Guarda todos los archivos.
2. Ejecuta el programa: `python src/main.py`
3. Selecciona tu nuevo tipo de documento.
4. Carga un PDF y dale a **INICIAR PROCESAMIENTO**.
5. Revisa la carpeta de salida para ver tus archivos `.txt` y `.md`.

---

## 💡 Consejos para la práctica
*   **Claves iguales**: Asegúrate de que la clave que pones en la Factoría (`'mi_doc'`) sea la misma que pones en la GUI.
*   **Mayúsculas/Minúsculas**: Python distingue entre ellas. Revisa bien los nombres de las clases.
*   **Logs**: Si algo falla, mira la ventana de "Log" en la aplicación, ahí te dirá el error exacto.

¡Mucho ánimo con la práctica! 💪
