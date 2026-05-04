import os
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from preprocess.core.factory import ProcessorFactory

class ProcessWorker(QThread):
    """
    Worker thread to process PDF files asynchronously,
    preventing the user interface from freezing during the operation.
    """
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, pdf_files, output_dir, generate_md, generate_txt, document_type):
        """
        Initializes the process worker.
        
        Args:
            pdf_files (list): List of paths to PDF files
            output_dir (str): Base directory for output
            generate_md (bool): Whether to generate Markdown reports
            generate_txt (bool): Whether to generate structured TXT folders
            document_type (str): Type of document to process
        """
        super().__init__()
        self.pdf_files = pdf_files
        self.output_dir = output_dir
        self.generate_md = generate_md
        self.generate_txt = generate_txt
        self.document_type = document_type
    
    def _get_unique_folder_name(self, base_dir, original_name):
        """
        Ensures a unique folder name by adding a numeric suffix if necessary.
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
        Main execution of the processing thread.
        """
        try:
            total = len(self.pdf_files)
            for idx, pdf_path in enumerate(self.pdf_files):
                self.log.emit(f"Processing: {Path(pdf_path).name}")
                
                try:
                    # Instantiate the appropriate processor through the factory
                    processor = ProcessorFactory.create_processor(pdf_path, self.document_type)
                    processor.process()
                    
                    # Organize by document type
                    type_folder = Path(self.output_dir) / self.document_type
                    type_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Define destination folder for this specific report
                    original_name = Path(pdf_path).stem
                    report_folder = self._get_unique_folder_name(type_folder, original_name)
                    report_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Export to structured format (TXT)
                    if self.generate_txt:
                        txt_dir = report_folder / "structured"
                        processor.get_structured_text(output_dir=str(txt_dir))
                    
                    # Export to Markdown format (MD)
                    if self.generate_md:
                        md_path = report_folder / "report.md"
                        processor.get_md(output_path=str(md_path))
                    
                    self.log.emit(f"✓ {Path(pdf_path).name} completed")
                
                except Exception as e:
                    self.log.emit(f"✗ Error in file {Path(pdf_path).name}: {str(e)}")
                
                # Update progress bar
                self.progress.emit(int((idx + 1) / total * 100))
            
            self.finished.emit(True, f"Processing finished. {total} file(s) processed.")
        
        except Exception as e:
            self.log.emit(f"✗ CRITICAL ERROR: {str(e)}")
            self.finished.emit(False, f"Critical error during process: {str(e)}")
