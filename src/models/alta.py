class HojaAlta:
    """Model representing a hospital discharge report."""
    
    def __init__(self, args):
        """
        Initializes the discharge report with extracted section data.
        
        Args:
            args (tuple): Data for the 10 standard discharge sections
        """
        # Mapping based on typical hospital discharge report sections
        (self.motivo, self.antecedentes, self.enfermedad, self.exploracion, 
         self.pComplementarias, self.evolucion, self.juicio, self.tratamiento, 
         self.plan, self.revisiones) = args

        self.secciones = {
            'motivo': self.motivo,
            'antecedentes': self.antecedentes,
            'enfermedad': self.enfermedad,
            'exploracion': self.exploracion,
            'pruebas': self.pComplementarias,
            'evolucion': self.evolucion,
            'juicio': self.juicio,
            'tratamiento': self.tratamiento,
            'plan': self.plan,
            'revisiones': self.revisiones
        }

    def __str__(self):
        return (f"--- DISCHARGE REPORT ---\n"
                f"Reason: {self.secciones['motivo']}\n"
                f"Clinical Judgment: {self.secciones['juicio']}\n"
                f"Plan: {self.secciones['plan']}")

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value
