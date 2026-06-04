import sys
import os
sys.path.append(os.path.abspath('src'))

from preprocess.readers.pdf_reader import PDFReader
text = PDFReader.read_pdf_text('2025_6 TC.pdf')
with open('scratch/pdf_text.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")
