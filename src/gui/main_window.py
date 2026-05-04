import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QProgressBar, QLabel, QTextEdit,
    QMessageBox, QRadioButton, QButtonGroup, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

from gui.worker import ProcessWorker

class MedicalReportApp(QMainWindow):
    """
    Ventana principal de la aplicación para el procesamiento de informes médicos.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Procesador de Informes Médicos")
        self.setGeometry(100, 100, 700, 600)
        self.setMinimumSize(600, 500)
        
        self.selected_files = []
        self.output_directory = str(Path.home() / "informes_procesados")
        self.worker = None
        self.document_type = "alta"
        
        self.init_ui()
    
    def init_ui(self):
        """
        Inicializa los componentes de la interfaz de usuario.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setCentralWidget(scroll)
        
        main_widget = QWidget()
        scroll.setWidget(main_widget)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Cabecera
        title = QLabel("Procesador de Informes Médicos")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Selección de tipo de documento
        layout.addWidget(QLabel("Seleccione el tipo de informe:"))
        radio_layout = QHBoxLayout()
        self.doc_type_group = QButtonGroup()
        
        types = [("Informe de Alta", "alta"), ("Anamnesis", "anamnesis"), ("Evolución", "evolucion")]
        for text, key in types:
            radio = QRadioButton(text)
            if key == "alta": radio.setChecked(True)
            radio.toggled.connect(lambda checked, k=key: self.on_doc_type_changed(k) if checked else None)
            self.doc_type_group.addButton(radio)
            radio_layout.addWidget(radio)
        
        radio_layout.addStretch()
        layout.addLayout(radio_layout)
        
        # Controles de carga de archivos
        btn_layout = QHBoxLayout()
        self.btn_add = self._create_styled_button("📄 Seleccionar Archivos", "#3498db", self.select_files)
        self.btn_folder = self._create_styled_button("📁 Seleccionar Carpeta", "#3498db", self.select_folder)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_folder)
        layout.addLayout(btn_layout)
        
        # Visualización de archivos seleccionados
        self.file_display = QLabel("No hay archivos seleccionados")
        self.file_display.setWordWrap(True)
        self.file_display.setStyleSheet("padding: 10px; background: #f9f9f9; border: 1px solid #ddd; border-radius: 4px;")
        layout.addWidget(self.file_display)
        
        # Opciones de exportación
        layout.addWidget(QLabel("Formatos de salida:"))
        format_layout = QHBoxLayout()
        self.btn_txt = QPushButton("Estructura TXT")
        self.btn_txt.setCheckable(True)
        self.btn_txt.setChecked(True)
        self.btn_md = QPushButton("Markdown (MD)")
        self.btn_md.setCheckable(True)
        self.btn_md.setChecked(True)
        format_layout.addWidget(self.btn_txt)
        format_layout.addWidget(self.btn_md)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Configuración de salida
        layout.addWidget(QLabel("Carpeta de destino:"))
        output_layout = QHBoxLayout()
        self.output_display = QLabel(self.output_directory)
        self.output_display.setWordWrap(True)
        self.output_display.setStyleSheet("padding: 8px; background: #f0f0f0; border-radius: 4px;")
        output_layout.addWidget(self.output_display, 1)
        
        btn_output = QPushButton("Cambiar")
        btn_output.clicked.connect(self.select_output_dir)
        output_layout.addWidget(btn_output)
        layout.addLayout(output_layout)
        
        # Indicadores de progreso y logs
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setVisible(False)
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet("background: #2c3e50; color: #ecf0f1; font-family: 'Consolas', monospace;")
        layout.addWidget(self.log_text)
        
        # Acciones finales
        action_layout = QHBoxLayout()
        btn_toggle = QPushButton("Alternar Log")
        btn_toggle.clicked.connect(self.toggle_log)
        action_layout.addWidget(btn_toggle)
        
        btn_open = QPushButton("Abrir Destino")
        btn_open.clicked.connect(self.open_output_folder)
        action_layout.addWidget(btn_open)
        
        action_layout.addStretch()
        self.btn_process = self._create_styled_button("INICIAR PROCESAMIENTO", "#27ae60", self.start_processing)
        self.btn_process.setMinimumWidth(200)
        action_layout.addWidget(self.btn_process)
        
        layout.addLayout(action_layout)
        layout.addStretch()
        main_widget.setLayout(layout)

    def _create_styled_button(self, text, color, callback):
        btn = QPushButton(text)
        btn.clicked.connect(callback)
        btn.setMinimumHeight(45)
        btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }}
            QPushButton:hover {{
                background-color: {color};
                opacity: 0.8;
            }}
        """)
        return btn

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar archivos PDF", "", "PDF (*.pdf)")
        if files:
            self.selected_files = files
            self.update_file_display()
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            pdf_files = list(Path(folder).glob("*.pdf"))
            if pdf_files:
                self.selected_files = [str(f) for f in pdf_files]
                self.update_file_display()
            else:
                QMessageBox.warning(self, "Aviso", "No se encontraron archivos PDF en la carpeta seleccionada.")
    
    def update_file_display(self):
        if not self.selected_files:
            self.file_display.setText("No hay archivos seleccionados")
        else:
            count = len(self.selected_files)
            names = "\n".join([f"• {Path(f).name}" for f in self.selected_files[:5]])
            if count > 5: names += f"\n... y {count - 5} más"
            self.file_display.setText(f"Archivos listos ({count}):\n{names}")
    
    def select_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino", self.output_directory)
        if folder:
            self.output_directory = folder
            self.output_display.setText(folder)
    
    def on_doc_type_changed(self, doc_type):
        self.document_type = doc_type
    
    def start_processing(self):
        if not self.selected_files:
            QMessageBox.warning(self, "Atención", "Debe seleccionar al menos un archivo PDF.")
            return
        
        if not (self.btn_txt.isChecked() or self.btn_md.isChecked()):
            QMessageBox.warning(self, "Atención", "Debe seleccionar al menos un formato de salida (TXT o MD).")
            return
        
        self.worker = ProcessWorker(
            self.selected_files, self.output_directory,
            self.btn_md.isChecked(), self.btn_txt.isChecked(), 
            self.document_type
        )
        
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log_message)
        self.worker.finished.connect(self.on_finished)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.log_text.setVisible(True)
        self.btn_process.setEnabled(False)
        
        self.worker.start()
    
    def log_message(self, message):
        self.log_text.insertPlainText(message + "\n")
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        QApplication.processEvents()
    
    def toggle_log(self):
        self.log_text.setVisible(not self.log_text.isVisible())
    
    def on_finished(self, success, message):
        self.btn_process.setEnabled(True)
        if success:
            QMessageBox.information(self, "Éxito", message)
        else:
            QMessageBox.critical(self, "Error", message)
    
    def open_output_folder(self):
        if sys.platform == "win32":
            os.startfile(self.output_directory)
        elif sys.platform == "darwin":
            os.system(f"open '{self.output_directory}'")
        else:
            os.system(f"xdg-open '{self.output_directory}'")
