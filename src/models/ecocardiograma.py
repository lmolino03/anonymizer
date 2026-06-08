class HojaEcocardiograma:
    """Model representing an ecocardiograma report."""
 
    def __init__(self, args):
        """
        Initializes the ecocardiograma report with extracted section data.
        
        Args:
            args (tuple): Data for the 4 standard ecocardiograma sections
        """
        (self.fecha_procedimiento,
         self.medidas,
         self.ecocardiograma,
         self.conclusiones) = args
 
        self.secciones = {
            'fecha_procedimiento': self.fecha_procedimiento,
            'medidas':             self.medidas,
            'ecocardiograma':      self.ecocardiograma,
            'conclusiones':        self.conclusiones,
        }
 
    def __str__(self):
        medidas_str       = self.secciones['medidas']       if self.secciones['medidas']       is not None else "N/A"
        ecocardiograma_str= self.secciones['ecocardiograma']if self.secciones['ecocardiograma'] is not None else "N/A"
        conclusiones_str  = self.secciones['conclusiones']  if self.secciones['conclusiones']   is not None else "N/A"
 
        return (f"--- ECOCARDIOGRAMA REPORT ---\n"
                f"Date procedure: {self.secciones['fecha_procedimiento']}\n"
                f"Measures: {medidas_str}\n"
                f"Ecocardiograma: {ecocardiograma_str}\n"
                f"Conclusions: {conclusiones_str}")
 
    def __getitem__(self, index):
        return self.secciones[index]
 
    def __setitem__(self, index, value):
        self.secciones[index] = value
 
    def __delitem__(self, index):
        del self.secciones[index]