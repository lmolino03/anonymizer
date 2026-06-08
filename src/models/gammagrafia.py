class HojaGammagrafia:
    """Model representing a gammagrafia report."""
 
    def __init__(self, args):
        """
        Initializes the gammagrafia report with extracted section data.
        
        Args:
            args (tuple): Data for the 7 standard gammagrafia sections
        """
        (self.fecha_informe,
         self.datos_clinicos,
         self.exploraciones,
         self.anatomias,
         self.hallazgos,
         self.conclusion,
         self.recomendaciones) = args
 
        self.secciones = {
            'fecha_de_informe': self.fecha_informe,
            'datos_clinicos':   self.datos_clinicos,
            'exploraciones':    self.exploraciones,
            'anatomias':        self.anatomias,
            'hallazgos':        self.hallazgos,
            'conclusion':       self.conclusion,
            'recomendaciones':  self.recomendaciones
        }
 
    def __str__(self):
        fecha_str           = self.secciones['fecha_de_informe'] if self.secciones['fecha_de_informe'] is not None else "N/A"
        datos_clinicos_str  = self.secciones['datos_clinicos']   if self.secciones['datos_clinicos']   is not None else "N/A"
        exploraciones_str   = self.secciones['exploraciones']    if self.secciones['exploraciones']    is not None else "N/A"
        anatomias_str       = self.secciones['anatomias']        if self.secciones['anatomias']        is not None else "N/A"
        hallazgos_str       = self.secciones['hallazgos']        if self.secciones['hallazgos']        is not None else "N/A"
        conclusion_str      = self.secciones['conclusion']       if self.secciones['conclusion']       is not None else "N/A"
        recomendaciones_str = self.secciones['recomendaciones']  if self.secciones['recomendaciones']  is not None else "N/A"
 
        return (f"--- GAMMAGRAFIA REPORT ---\n"
                f"Report Date: {fecha_str}\n"
                f"Clinical Data: {datos_clinicos_str}\n"
                f"Explorations: {exploraciones_str}\n"
                f"Anatomical Findings: {anatomias_str}\n"
                f"Findings: {hallazgos_str}\n"
                f"Conclusion: {conclusion_str}\n"
                f"Recommendations: {recomendaciones_str}")
 
    def __getitem__(self, index):
        return self.secciones[index]
 
    def __setitem__(self, index, value):
        self.secciones[index] = value
 
    def __delitem__(self, index):
        del self.secciones[index]
