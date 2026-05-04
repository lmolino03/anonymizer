import sys
import os
from pathlib import Path

# Add 'src' directory to path if running from root to resolve imports
src_path = str(Path(__file__).parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from PyQt6.QtWidgets import QApplication
from gui.main_window import MedicalReportApp

def main():
    """
    Main entry point of the application.
    """
    app = QApplication(sys.argv)
    
    # Global style configuration (optional)
    app.setStyle("Fusion")
    
    window = MedicalReportApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()