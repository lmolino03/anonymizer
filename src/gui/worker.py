import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from preprocess.core.factory import ProcessorFactory

class ProcessWorker(QThread):
    """
    Hilo de trabajo para procesar archivos PDF de forma asíncrona,
    evitando que la interfaz de usuario se congele durante la operación.
    """
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, pdf_files, output_dir, generate_md, generate_txt, document_type):
        super().__init__()
        self.pdf_files = pdf_files
        self.output_dir = output_dir
        self.generate_md = generate_md
        self.generate_txt = generate_txt
        self.document_type = document_type
    
    def _get_unique_folder_name(self, base_dir, original_name):
        """
        Garantiza un nombre de carpeta único añadiendo un sufijo numérico si es necesario.
        """
        target_folder = base_dir / original_name
        if not target_folder.exists():
            return target_folder
        
        counter = 1
        while True:
            target_folder = base_dir / f"{original_name}_{counter}"
            if not target_folder.exists():
                return target_folder
            counter += 1
    
    def run(self):
        """
        Ejecución principal del hilo de procesamiento.
        """
        try:
            total = len(self.pdf_files)
            for idx, pdf_path in enumerate(self.pdf_files):
                self.log.emit(f"Procesando: {Path(pdf_path).name}")
                
                try:
                    # Instanciar el procesador adecuado mediante la factoría
                    processor = ProcessorFactory.create_processor(pdf_path, self.document_type)
                    processor.process()
                    
                    # Organizar por tipo de documento
                    type_folder = Path(self.output_dir) / self.document_type
                    type_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Definir carpeta de destino para este informe específico
                    original_name = Path(pdf_path).stem
                    report_folder = self._get_unique_folder_name(type_folder, original_name)
                    report_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Exportación a formato estructurado (TXT)
                    if self.generate_txt:
                        txt_dir = report_folder / "estructurado"
                        processor.get_structured_text(output_dir=str(txt_dir))
                    
                    # Exportación a formato Markdown (MD)
                    if self.generate_md:
                        md_path = report_folder / "informe.md"
                        processor.get_md(output_path=str(md_path))
                    
                    self.log.emit(f"✓ {Path(pdf_path).name} completado")
                
                except Exception as e:
                    self.log.emit(f"✗ Error en archivo {Path(pdf_path).name}: {str(e)}")
                
                # Actualizar barra de progreso
                self.progress.emit(int((idx + 1) / total * 100))
            
            self.finished.emit(True, f"Procesamiento finalizado. {total} archivo(s) procesado(s).")
        
        except Exception as e:
            self.log.emit(f"✗ ERROR CRÍTICO: {str(e)}")
            self.finished.emit(False, f"Error crítico durante el proceso: {str(e)}")
