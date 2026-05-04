class HojaAlta:
    def __init__(self, args):
        # Mapeo basado en las secciones típicas de un informe de alta
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
        return (f"--- INFORME DE ALTA ---\n"
                f"Motivo: {self.secciones['motivo']}\n"
                f"Juicio Clínico: {self.secciones['juicio']}\n"
                f"Plan: {self.secciones['plan']}")

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value
