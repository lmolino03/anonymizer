class RegistroEvolucion:
    """Representa una fila/registro individual en la hoja de evolución."""
    def __init__(self, fila, pagina, secciones):
        self.fila = fila
        self.pagina = pagina
        self.secciones = secciones  # Diccionario {nombre_seccion: cuerpo}

    def __str__(self):
        return f"Registro (Fila {self.fila}, Pag {self.pagina}): {list(self.secciones.keys())}"

class HojaEvolucion:
    """Representa el conjunto de registros de una hoja de evolución."""
    def __init__(self, registros=None):
        self.registros = registros if registros else []

    def agregar_registro(self, registro):
        self.registros.append(registro)

    def __len__(self):
        return len(self.registros)

    def __iter__(self):
        return iter(self.registros)
