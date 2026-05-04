class RegistroEvolucion:
    """Represents an individual row/record in the evolution sheet."""
    def __init__(self, fila, pagina, secciones):
        """
        Initializes an evolution record.
        
        Args:
            fila (int): Row index
            pagina (int): Page number
            secciones (dict): Dictionary mapping section names to their bodies
        """
        self.fila = fila
        self.pagina = pagina
        self.secciones = secciones  # Dictionary {section_name: body}

    def __str__(self):
        return f"Record (Row {self.fila}, Page {self.pagina}): {list(self.secciones.keys())}"

class HojaEvolucion:
    """Represents the set of records in an evolution sheet."""
    def __init__(self, registros=None):
        """
        Initializes the evolution sheet.
        
        Args:
            registros (list, optional): List of RegistroEvolucion instances
        """
        self.registros = registros if registros else []

    def agregar_registro(self, registro):
        """Adds a record to the sheet."""
        self.registros.append(registro)

    def __len__(self):
        return len(self.registros)

    def __iter__(self):
        return iter(self.registros)
