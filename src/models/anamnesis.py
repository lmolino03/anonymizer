class HojaAnamnesis:
    """Model representing a medical anamnesis report."""
    
    def __init__(self, args):
        """
        Initializes the anamnesis report with extracted section data.
        
        Args:
            args (tuple): Data for the 7 standard anamnesis sections
        """
        self.motivo, self.antecedentes, self.enfermedad, self.exploracion, self.pComplementarias, self.juicio, self.plan = args

        self.secciones = {
            'motivo': self.motivo,
            'antecedentes': self.antecedentes,
            'enfermedad': self.enfermedad,
            'exploracion': self.exploracion,
            'pruebas': self.pComplementarias,
            'juicio': self.juicio,
            'plan': self.plan
        }

    def __str__(self):
        exploracion_str = self.secciones['exploracion'] if self.secciones['exploracion'] is not None else "N/A"
        pruebas_str = self.secciones['pruebas'] if self.secciones['pruebas'] is not None else "N/A"
        plan_str = self.secciones['plan'] if self.secciones['plan'] is not None else "N/A"

        return (f"Reason for consultation: {self.secciones['motivo']}\n"
                f"Background: {self.secciones['antecedentes']}\n"
                f"Current Illness: {self.secciones['enfermedad']}\n"
                f"Examination: {exploracion_str}\n"
                f"Complementary tests: {pruebas_str}\n"
                f"Clinical judgment: {self.secciones['juicio']}\n"
                f"Action plan: {plan_str}")

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value

    def __delitem__(self, index):
        del self.secciones[index]

class Antecedentes():
    """Model representing medical background (history)."""
    
    def __init__(self, args):
        """
        Initializes background data.
        
        Args:
            args (tuple): (personal background, family background)
        """
        self.personales, self.familiares = args

        self.secciones = {
            'personales': self.personales,
            'familiares': self.familiares,
        }

    def __str__(self):
        familiares_str = self.secciones['familiares'] if self.secciones['familiares'] is not None else "N/A"
        return f"{self.secciones['personales']}\nFamily History: {familiares_str} "

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value

    def __delitem__(self, index):
        del self.secciones[index]
