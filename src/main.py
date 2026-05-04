import sys
import os
from pathlib import Path

# Añadir el directorio 'src' al path si se ejecuta desde la raíz para resolver importaciones
src_path = str(Path(__file__).parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from PyQt6.QtWidgets import QApplication
from gui.main_window import MedicalReportApp

def main():
    """
    Punto de entrada principal de la aplicación.
    """
    app = QApplication(sys.argv)
    
    # Configuración de estilo global (opcional)
    app.setStyle("Fusion")
    
    window = MedicalReportApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()