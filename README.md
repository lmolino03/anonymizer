# ANONIMIZADOR - Clinical Report Processing System

A comprehensive system designed for processing, anonymizing, and structuring clinical reports in PDF format. The system features advanced table detection and automatic content organization to facilitate clinical data analysis.

---

## 1. Overview

**ANONIMIZADOR** transforms unstructured medical documents into processable and readable formats while maintaining data integrity and organizing information into logical sections. The system is particularly robust in processing complex Evolution Sheets with dense tabular structures.

### Supported Document Types
*   **Hospital Discharge Reports**: Standard section extraction and metadata cleaning.
*   **Anamnesis (Medical History)**: Hierarchical processing of patient background and consultation motives.
*   **Evolution Sheets**: Advanced table analysis and multi-page record grouping.

### Output Formats
*   **Markdown (.md)**: Structured reports ready for professional viewing.
*   **Structured TXT**: Directory-based organization of section files.

---

## 2. Installation and Usage

### System Requirements
*   Python 3.8 or higher.
*   Dependencies: PyMuPDF (fitz), PyQt6, numpy, pypandoc.

### Recommended Installation (Conda)
It is highly recommended to use **Conda** (or Miniconda) for environment management:

```bash
# 1. Create the virtual environment with Python 3.10
conda create -n anonimizador python=3.10 -y

# 2. Activate the environment
conda activate anonimizador

# 3. Install all dependencies
pip install -r requirements.txt
```

### Running the Graphical Interface (GUI)
The main application allows visual batch processing:
```bash
python src/main.py
```

### Analysis Tool (EDA)
To perform technical analysis of a PDF structure from the command line:
```bash
python src/eda.py path/to/file.pdf --json output.json --tables
```

### Executable Generation (.exe)
To compile the application into a standalone Windows executable, use the optimized PyInstaller configuration:

```bash
# Generate the executable (will use anonimizador.spec automatically)
pyinstaller anonimizador.spec --clean
```
*   **Output**: The executable will be generated in `dist/ANONIMIZADOR.exe`.
*   **Icon**: Automatically includes the official project icon.
*   **Portability**: The file in `dist` is all you need to run the app on any Windows machine without Python.

---

## 3. System Architecture

The project follows a modular architecture based on design patterns for easy maintenance and extensibility:

### Directory Structure
*   **src/**: Main source code.
    *   **gui/**: GUI modules and asynchronous workers.
    *   **models/**: Formal data structures for report representation (`HojaAlta`, `HojaAnamnesis`, etc.).
    *   **preprocess/**: Business logic divided into:
        *   **core/**: Base classes and abstractions.
        *   **handlers/**: Specific processors for each document type.
        *   **readers/**: PDF reading and analysis engines.
    *   **utils/**: Transversal utilities and cleaning functions.
*   **tests/**: Unit and integration test suite.

### Key Components
*   **ProcessorFactory**: Responsible for instantiating the correct processor based on document type.
*   **BaseProcessor**: Defines the standard workflow (Read -> Clean -> Extract -> Validate).
*   **PDFLineAnalyzer**: Specialized engine for table detection and structural text positioning.

---

## 4. Technical Processing Guide

### Evolution Sheets Workflow
1.  **Table Detection**: The system identifies the coordinates of every cell in the document.
2.  **Structural Mapping**: Each text fragment is linked to its corresponding cell based on its absolute PDF position.
3.  **Multi-page Consolidation**: Records continuing across successive pages are automatically detected and unified.
4.  **Output Generation**: A folder structure is created reflecting the chronological organization of clinical records.

### Extending Functionality
To implement support for new document types, create a new "handler" inheriting from `BaseProcessor` and register it in the central factory.

---

## 5. Version History

### Version 3.0.0
*   Professional modular restructuring of the source code.
*   Implementation of advanced table processing and structural mapping.
*   Unified technical documentation.

### Version 2.0.0
*   Markdown generation support for all report types.
*   Updated GUI for batch processing.

---

**Last Update:** May 2024
**Project Status:** Stable / Production
