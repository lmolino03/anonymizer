class HojaAnamnesis:
    def __init__(self, args):
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

        return f"Motivo de consulta: {self.secciones['motivo']}\nAntecedentes: {self.secciones['antecedentes']}\nEnfermedad Actual: {self.secciones['enfermedad']}\nExploración: {exploracion_str}\nPruebas complementarias: {pruebas_str}\nJuicio clínico: {self.secciones['juicio']}\nPlan de actuación: {plan_str}"

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value

    def __delitem__(self, index):
        del self.secciones[index]

class Antecedentes():
    def __init__(self, args):
        self.personales, self.familiares = args

        self.secciones = {
            'personales': self.personales,
            'familiares': self.familiares,
        }

    def __str__(self):
        familiares_str = self.secciones['familiares'] if self.secciones['familiares'] is not None else "N/A"
        return f"{self.secciones['personales']}\nFamiliares: {familiares_str} "

    def __getitem__(self, index):
        return self.secciones[index]

    def __setitem__(self, index, value):
        self.secciones[index] = value

    def __delitem__(self, index):
        del self.secciones[index]
