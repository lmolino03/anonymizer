import pymupdf as fitz  # PyMuPDF
import json
import re
import csv
import os

from collections import defaultdict

class PDFLineAnalyzer:
   """
   Advanced PDF analyzer that extracts detailed line-by-line information,
   detects tables, and classifies text according to its location.
   """
  
   def __init__(self, pdf_path):
       """
       Initializes the analyzer with the PDF path.
      
       Args:
           pdf_path (str): Path to the PDF file to analyze
       """
       self.pdf_path = pdf_path
       self.doc = fitz.open(pdf_path)
       self.analysis_results = []
  
   def rgb_to_hex(self, rgb_tuple):
       """Converts RGB tuple (0-1) to hexadecimal."""
       if not rgb_tuple or len(rgb_tuple) != 3:
           return "#000000"
       return "#{:02x}{:02x}{:02x}".format(
           int(rgb_tuple[0] * 255),
           int(rgb_tuple[1] * 255),
           int(rgb_tuple[2] * 255)
       )
  
   def int_to_rgb(self, color_int):
       """Converts integer color to RGB tuple (0-1)."""
       if color_int == 0:
           return (0, 0, 0)
      
       r = (color_int >> 16) & 255
       g = (color_int >> 8) & 255
       b = color_int & 255
      
       return (r/255.0, g/255.0, b/255.0)
  
   def get_font_flags_description(self, flags):
       """Interprets PyMuPDF font flags."""
       descriptions = []
       if flags & 2**4:  # bit 4: bold
           descriptions.append("bold")
       if flags & 2**1:  # bit 1: italic
           descriptions.append("italic")
       if flags & 2**0:  # bit 0: superscript
           descriptions.append("superscript")
       if flags & 2**2:  # bit 2: monospace
           descriptions.append("monospace")
       return descriptions if descriptions else ["normal"]
  
   def calculate_indentation(self, x0, page_width):
       """Calculates indentation as a percentage of page width."""
       return {
           "pixels": round(x0, 2),
           "percentage": round((x0 / page_width) * 100, 2)
       }
  
   def detect_tables_by_lines(self, page):
       """
       Detects tables using lines and rectangles drawn in the PDF.
       More precise method for PDFs with explicit borders.
       """
       drawings = page.get_drawings()
      
       h_lines = []
       v_lines = []
       rectangles = []
      
       for drawing in drawings:
           for item in drawing["items"]:
               if item[0] == "l":  # line
                   p1, p2 = item[1], item[2]
                  
                   # Horizontal line
                   if abs(p1.y - p2.y) < 2:
                       h_lines.append({
                           "y": round((p1.y + p2.y) / 2, 2),
                           "x1": round(min(p1.x, p2.x), 2),
                           "x2": round(max(p1.x, p2.x), 2),
                           "length": abs(p2.x - p1.x)
                       })
                  
                   # Vertical line
                   if abs(p1.x - p2.x) < 2:
                       v_lines.append({
                           "x": round((p1.x + p2.x) / 2, 2),
                           "y1": round(min(p1.y, p2.y), 2),
                           "y2": round(max(p1.y, p2.y), 2),
                           "length": abs(p2.y - p1.y)
                       })
              
               elif item[0] == "re":  # rectangle
                   rect = item[1]
                   rectangles.append({
                       "x0": round(rect.x0, 2),
                       "y0": round(rect.y0, 2),
                       "x1": round(rect.x1, 2),
                       "y1": round(rect.y1, 2)
                   })
      
       return h_lines, v_lines, rectangles
  
   def cluster_coordinates(self, coords, tolerance=3):
       """Groups close coordinates to detect consistent lines."""
       if not coords:
           return []
      
       sorted_coords = sorted(set(coords))
       clusters = [[sorted_coords[0]]]
      
       for coord in sorted_coords[1:]:
           if coord - clusters[-1][-1] <= tolerance:
               clusters[-1].append(coord)
           else:
               clusters.append([coord])
      
       return [round(sum(cluster) / len(cluster), 2) for cluster in clusters]
  
   def are_lines_consistent(self, h_lines, v_lines, y_coords, x_coords):
       """Verifies if lines form a consistent table."""
       consistent_h = 0
       for y in y_coords:
           h_line = next((l for l in h_lines if abs(l["y"] - y) < 3), None)
           if h_line:
               crossing = sum(1 for x in x_coords
                            if h_line["x1"] <= x <= h_line["x2"] or
                               h_line["x2"] >= x >= h_line["x1"])
               if crossing >= 2:
                   consistent_h += 1
      
       return consistent_h >= 2
  
   def create_table_from_lines(self, y_coords, x_coords):
       """Creates table structure from coordinates."""
       cells = []
       for i in range(len(y_coords) - 1):
           row = []
           for j in range(len(x_coords) - 1):
               cell = {
                   "row": i,
                   "column": j,
                   "bbox": [
                       x_coords[j],
                       y_coords[i],
                       x_coords[j + 1],
                       y_coords[i + 1]
                   ],
                   "text": ""
               }
               row.append(cell)
           cells.append(row)
      
       return {
           "bbox": [x_coords[0], y_coords[0], x_coords[-1], y_coords[-1]],
           "num_rows": len(y_coords) - 1,
           "num_columns": len(x_coords) - 1,
           "rows_y": y_coords,
           "columns_x": x_coords,
           "cells": cells
       }
  
   def find_table_structure(self, h_lines, v_lines, rectangles, min_lines=3):
       """Finds actual table structure based on significant lines."""
       tables = []
      
       if not h_lines or not v_lines:
           return tables
      
       # Filter very short lines
       h_lines = [l for l in h_lines if l["length"] > 30]
       v_lines = [l for l in v_lines if l["length"] > 20]
      
       if len(h_lines) < 2 or len(v_lines) < 2:
           return tables
      
       # Group close lines
       h_groups = self.cluster_coordinates([l["y"] for l in h_lines], tolerance=3)
       v_groups = self.cluster_coordinates([l["x"] for l in v_lines], tolerance=3)
      
       if len(h_groups) < 2 or len(v_groups) < 2:
           return tables
      
       # Search for tables within rectangles
       for rect in rectangles:
           rect_h_lines = [h for h in h_groups if rect["y0"] <= h <= rect["y1"]]
           rect_v_lines = [v for v in v_groups if rect["x0"] <= v <= rect["x1"]]
          
           if len(rect_h_lines) >= 2 and len(rect_v_lines) >= 2:
               table = self.create_table_from_lines(
                   sorted(rect_h_lines),
                   sorted(rect_v_lines)
               )
               tables.append(table)
               return tables
      
       # If no rectangles, look for groupings
       if not tables:
           y_coords = sorted(h_groups)
           x_coords = sorted(v_groups)
          
           if self.are_lines_consistent(h_lines, v_lines, y_coords, x_coords):
               table = self.create_table_from_lines(y_coords, x_coords)
               tables.append(table)
      
       return tables
  
   def detect_tables_by_text_alignment(self, all_spans, page_width, page_height):
       """Detects tables by analyzing text alignment (fallback)."""
       if len(all_spans) < 10:
           return []
      
       # Group spans by rows
       rows = defaultdict(list)
       for span in all_spans:
           y = round(span["bbox"][1])
           rows[y].append(span)
      
       # Analyze patterns
       row_patterns = []
       for y in sorted(rows.keys()):
           x_positions = sorted([span["bbox"][0] for span in rows[y]])
           row_patterns.append({
               "y": y,
               "x_positions": x_positions,
               "num_elements": len(x_positions)
           })
      
       # Search for sequences with similar columns
       tables = []
       i = 0
       while i < len(row_patterns) - 2:
           sequence = [row_patterns[i]]
          
           for j in range(i + 1, min(i + 20, len(row_patterns))):
               if abs(row_patterns[j]["num_elements"] - row_patterns[i]["num_elements"]) <= 1:
                   if self.have_similar_x_alignment(
                       row_patterns[i]["x_positions"],
                       row_patterns[j]["x_positions"]
                   ):
                       sequence.append(row_patterns[j])
               elif len(sequence) >= 3:
                   break
          
           if len(sequence) >= 3:
               table = self.create_table_from_sequence(sequence)
               tables.append(table)
               i += len(sequence)
           else:
               i += 1
      
       return tables
  
   def have_similar_x_alignment(self, x_pos1, x_pos2, tolerance=15):
       """Verifies if two rows have similar X alignment."""
       if len(x_pos1) != len(x_pos2):
           return False
      
       differences = [abs(x1 - x2) for x1, x2 in zip(x_pos1, x_pos2)]
       return all(d < tolerance for d in differences)
  
   def create_table_from_sequence(self, sequence):
       """Creates a table from a sequence of aligned rows."""
       all_x = []
       for row in sequence:
           all_x.extend(row["x_positions"])
      
       x_coords = self.cluster_coordinates(all_x, tolerance=10)
       y_coords = [row["y"] for row in sequence]
       y_coords.append(y_coords[-1] + 20)
      
       return self.create_table_from_lines(y_coords, x_coords)
  
   def find_text_in_cell(self, cell_bbox, all_spans):
       """Finds text within a specific cell."""
       x0, y0, x1, y1 = cell_bbox
       texts = []
      
       for span in all_spans:
           span_x0, span_y0, span_x1, span_y1 = span["bbox"]
           center_x = (span_x0 + span_x1) / 2
           center_y = (span_y0 + span_y1) / 2
          
           if x0 <= center_x <= x1 and y0 <= center_y <= y1:
               texts.append(span["texto"])
      
       return " ".join(texts).strip()
  
   def analyze_table_content(self, table, all_spans):
       """Analyzes text content in each table cell."""
       for row in table["cells"]:
           for cell in row:
               cell["text"] = self.find_text_in_cell(cell["bbox"], all_spans)
       return table
  
   def classify_line_location(self, line_bbox, tables):
       """Classifies if a line is within a table and in which cell."""
       x0, y0, x1, y1 = line_bbox
       line_center_x = (x0 + x1) / 2
       line_center_y = (y0 + y1) / 2
      
       for table_idx, table in enumerate(tables):
           table_x0, table_y0, table_x1, table_y1 = table["bbox"]
          
           if (x0 >= table_x0 - 5 and x1 <= table_x1 + 5 and
               y0 >= table_y0 - 5 and y1 <= table_y1 + 5):
              
               for row_idx, row in enumerate(table["cells"]):
                   for col_idx, cell in enumerate(row):
                       cell_x0, cell_y0, cell_x1, cell_y1 = cell["bbox"]
                      
                       if (cell_x0 <= line_center_x <= cell_x1 and
                           cell_y0 <= line_center_y <= cell_y1):
                          
                           return {
                               "ubicacion": "dentro_tabla",
                               "tabla_id": table_idx,
                               "fila": row_idx,
                               "columna": col_idx,
                               "celda_bbox": cell["bbox"]
                           }
      
       return {
           "ubicacion": "fuera_tabla",
           "tabla_id": None,
           "fila": None,
           "columna": None,
           "celda_bbox": None
       }
  
   def group_spans_into_lines(self, spans):
       """Groups spans into lines based on similar Y coordinates."""
       lines = defaultdict(list)
       tolerance = 2
      
       for span in spans:
           y_coord = round(span["bbox"][1])
          
           found_line = None
           for line_y in lines.keys():
               if abs(line_y - y_coord) <= tolerance:
                   found_line = line_y
                   break
          
           if found_line is not None:
               lines[found_line].append(span)
           else:
               lines[y_coord].append(span)
      
       for line_y in lines:
           lines[line_y].sort(key=lambda x: x["bbox"][0])
      
       return dict(lines)
  
   def is_likely_title(self, text, font_size):
       """Determines if a line is likely a title."""
       avg_font_size = 12
       return (font_size > avg_font_size * 1.2 or
               text.isupper() or
               len(text.split()) <= 6)
  
   def analyze_page(self, page_num):
       """Analyzes a specific PDF page."""
       page = self.doc[page_num]
       page_dict = page.get_text("dict")
      
       page_width = page.rect.width
       page_height = page.rect.height
      
       page_analysis = {
           "pagina": page_num + 1,
           "dimensiones": {
               "ancho": round(page_width, 2),
               "alto": round(page_height, 2)
           },
           "tablas": [],
           "lineas": []
       }
      
       # Extract all text spans
       all_spans = []
       for block in page_dict["blocks"]:
           if "lines" in block:
               for line in block["lines"]:
                   for span in line["spans"]:
                       span_info = {
                           "texto": span["text"],
                           "bbox": span["bbox"],
                           "fuente": span["font"],
                           "tamaño": round(span["size"], 2),
                           "flags": span["flags"],
                           "color": span.get("color", 0)
                       }
                       if span_info["texto"].strip():
                           all_spans.append(span_info)
      
       # Detect tables (Method 1: drawn lines)
       h_lines, v_lines, rectangles = self.detect_tables_by_lines(page)
       tables_by_lines = self.find_table_structure(h_lines, v_lines, rectangles)
      
       # Method 2: text alignment (fallback)
       if not tables_by_lines:
           tables_by_lines = self.detect_tables_by_text_alignment(
               all_spans, page_width, page_height
           )
      
       # Analyze table content
       for table in tables_by_lines:
           table = self.analyze_table_content(table, all_spans)
           page_analysis["tablas"].append(table)
      
       # Group spans into lines
       lines_dict = self.group_spans_into_lines(all_spans)
      
       # Process each line
       for line_y in sorted(lines_dict.keys()):
           spans_in_line = lines_dict[line_y]
          
           full_text = "".join([span["texto"] for span in spans_in_line])
           first_span = spans_in_line[0]
           x0 = first_span["bbox"][0]
           main_span = max(spans_in_line, key=lambda x: len(x["texto"]))
          
           # Calculate full line bbox
           line_bbox = [
               min([s["bbox"][0] for s in spans_in_line]),
               min([s["bbox"][1] for s in spans_in_line]),
               max([s["bbox"][2] for s in spans_in_line]),
               max([s["bbox"][3] for s in spans_in_line])
           ]
          
           # Classify location
           ubicacion_info = self.classify_line_location(
               line_bbox, page_analysis["tablas"]
           )
          
           line_analysis = {
               "numero_linea": len(page_analysis["lineas"]) + 1,
               "texto_completo": full_text,
               "posicion": {
                   "y_superior": round(line_y, 2),
                   "y_inferior": round(max([s["bbox"][3] for s in spans_in_line]), 2),
                   "x_inicio": round(x0, 2),
                   "x_final": round(max([s["bbox"][2] for s in spans_in_line]), 2)
               },
               "sangria": self.calculate_indentation(x0, page_width),
               "ubicacion_tabla": ubicacion_info,
               "formato_principal": {
                   "fuente": main_span["fuente"],
                   "tamaño": main_span["tamaño"],
                   "color_hex": self.rgb_to_hex(self.int_to_rgb(main_span["color"])),
                   "color_rgb": self.int_to_rgb(main_span["color"]),
                   "estilos": self.get_font_flags_description(main_span["flags"])
               },
               "spans_detallados": []
           }
          
           # Details per span
           for i, span in enumerate(spans_in_line):
               span_detail = {
                   "span_numero": i + 1,
                   "texto": span["texto"],
                   "posicion": {
                       "x0": round(span["bbox"][0], 2),
                       "y0": round(span["bbox"][1], 2),
                       "x1": round(span["bbox"][2], 2),
                       "y1": round(span["bbox"][3], 2)
                   },
                   "fuente": span["fuente"],
                   "tamaño": span["tamaño"],
                   "color_hex": self.rgb_to_hex(self.int_to_rgb(span["color"])),
                   "color_rgb": self.int_to_rgb(span["color"]),
                   "estilos": self.get_font_flags_description(span["flags"])
               }
               line_analysis["spans_detallados"].append(span_detail)
          
           # Metadata
           line_analysis["metadatos"] = {
               "longitud_caracteres": len(full_text),
               "num_palabras": len(full_text.split()),
               "num_spans": len(spans_in_line),
               "es_titulo": self.is_likely_title(full_text, main_span["tamaño"]),
               "tiene_numeros": bool(re.search(r'\d', full_text)),
               "es_mayusculas": full_text.isupper(),
               "espacios_iniciales": len(full_text) - len(full_text.lstrip()),
               "espacios_finales": len(full_text) - len(full_text.rstrip())
           }
          
           page_analysis["lineas"].append(line_analysis)
      
       return page_analysis
  
   def analyze_full_document(self):
       """Analyzes the entire PDF document."""
       full_analysis = {
           "archivo": self.pdf_path,
           "total_paginas": len(self.doc),
           "metadatos": self.doc.metadata,
           "paginas": []
       }
      
       for page_num in range(len(self.doc)):
           page_analysis = self.analyze_page(page_num)
           full_analysis["paginas"].append(page_analysis)
      
       self.analysis_results = full_analysis
       return full_analysis

   def save_to_json(self, output_path):
       """Saves analysis in JSON format."""
       with open(output_path, 'w', encoding='utf-8') as f:
           json.dump(self.analysis_results, f, ensure_ascii=False, indent=2)
       print(f"Analysis saved to: {output_path}")
  
   def save_to_txt(self, output_path):
       """Saves analysis in readable TXT format."""
       if not self.analysis_results:
           print("No analysis available to save.")
           return
      
       with open(output_path, 'w', encoding='utf-8') as f:
           f.write("="*100 + "\n")
           f.write(f"DETAILED PDF ANALYSIS: {self.analysis_results['archivo']}\n")
           f.write("="*100 + "\n\n")
          
           f.write(f"GENERAL INFORMATION:\n")
           f.write(f"- Total pages: {self.analysis_results['total_paginas']}\n")
           f.write(f"- File: {self.analysis_results['archivo']}\n\n")
          
           if self.analysis_results['metadatos']:
               f.write("DOCUMENT METADATA:\n")
               for key, value in self.analysis_results['metadatos'].items():
                   if value:
                       f.write(f"- {key}: {value}\n")
               f.write("\n")
          
           for page in self.analysis_results['paginas']:
               f.write("="*80 + "\n")
               f.write(f"PAGE {page['pagina']}\n")
               f.write("="*80 + "\n")
               f.write(f"Dimensions: {page['dimensiones']['ancho']} x {page['dimensiones']['alto']} pixels\n")
               f.write(f"Total lines: {len(page['lineas'])}\n")
               f.write(f"Total detected tables: {len(page['tablas'])}\n\n")
              
               # Table information
               if page['tablas']:
                   f.write("DETECTED TABLES:\n")
                   for idx, table in enumerate(page['tablas']):
                       f.write(f"\n  TABLE {idx + 1}:\n")
                       f.write(f"  - Position: X({table['bbox'][0]:.1f}-{table['bbox'][2]:.1f}) Y({table['bbox'][1]:.1f}-{table['bbox'][3]:.1f})\n")
                       f.write(f"  - Dimensions: {table['num_rows']} rows x {table['num_columns']} columns\n")
                       f.write(f"  - Cell content:\n")
                      
                       for row_idx, row in enumerate(table['cells']):
                           f.write(f"    Row {row_idx + 1}: ")
                           cell_texts = [f"[{cell['text'][:30] if cell['text'] else 'empty'}]" for cell in row]
                           f.write(" | ".join(cell_texts) + "\n")
                       f.write("\n")
              
               # Line by line analysis
               for line in page['lineas']:
                   f.write("-"*60 + "\n")
                   f.write(f"LINE {line['numero_linea']}\n")
                   f.write("-"*60 + "\n")
                  
                   f.write(f"TEXT: '{line['texto_completo']}'\n\n")
                  
                   # Table location
                   ubi = line['ubicacion_tabla']
                   if ubi['ubicacion'] == 'dentro_tabla':
                       f.write("TABLE LOCATION:\n")
                       f.write(f"- This line is WITHIN a table\n")
                       f.write(f"- Table ID: {ubi['tabla_id']}\n")
                       f.write(f"- Row: {ubi['fila'] + 1}\n")
                       f.write(f"- Column: {ubi['columna'] + 1}\n")
                       f.write(f"- Cell BBox: {ubi['celda_bbox']}\n\n")
                   else:
                       f.write("LOCATION: Outside tables (free text)\n\n")
                  
                   f.write("POSITION AND INDENTATION:\n")
                   f.write(f"- Upper Y coordinate: {line['posicion']['y_superior']} px\n")
                   f.write(f"- Lower Y coordinate: {line['posicion']['y_inferior']} px\n")
                   f.write(f"- Start X coordinate: {line['posicion']['x_inicio']} px\n")
                   f.write(f"- End X coordinate: {line['posicion']['x_final']} px\n")
                   f.write(f"- Left indentation: {line['sangria']['pixels']} px ({line['sangria']['percentage']}% of width)\n\n")
                  
                   f.write("MAIN FORMAT:\n")
                   formato = line['formato_principal']
                   f.write(f"- Font: {formato['fuente']}\n")
                   f.write(f"- Size: {formato['tamaño']} points\n")
                   f.write(f"- Color (hex): {formato['color_hex']}\n")
                   f.write(f"- Color (RGB): {formato['color_rgb']}\n")
                   f.write(f"- Styles: {', '.join(formato['estilos'])}\n\n")
                  
                   f.write("ADDITIONAL METADATA:\n")
                   meta = line['metadatos']
                   f.write(f"- Length in characters: {meta['longitud_caracteres']}\n")
                   f.write(f"- Word count: {meta['num_palabras']}\n")
                   f.write(f"- Span count: {meta['num_spans']}\n")
                   f.write(f"- Likely title: {'Yes' if meta['es_titulo'] else 'No'}\n")
                   f.write(f"- Contains numbers: {'Yes' if meta['tiene_numeros'] else 'No'}\n")
                   f.write(f"- All caps: {'Yes' if meta['es_mayusculas'] else 'No'}\n")
                   f.write(f"- Leading spaces: {meta['espacios_iniciales']}\n")
                   f.write(f"- Trailing spaces: {meta['espacios_finales']}\n\n")
                  
                   if len(line['spans_detallados']) > 1:
                       f.write("SPAN DETAILS:\n")
                       for span in line['spans_detallados']:
                           f.write(f"  SPAN {span['span_numero']}:\n")
                           f.write(f"    - Text: '{span['texto']}'\n")
                           f.write(f"    - Position: X({span['posicion']['x0']}-{span['posicion']['x1']}) Y({span['posicion']['y0']}-{span['posicion']['y1']})\n")
                           f.write(f"    - Font: {span['fuente']}\n")
                           f.write(f"    - Size: {span['tamaño']} pt\n")
                           f.write(f"    - Color: {span['color_hex']} {span['color_rgb']}\n")
                           f.write(f"    - Styles: {', '.join(span['estilos'])}\n")
                       f.write("\n")
              
               f.write("\n")
      
       print(f"Detailed analysis saved in TXT: {output_path}")
  
   def print_summary(self):
       """Prints analysis summary to console."""
       if not self.analysis_results:
           print("No analysis available. Run analyze_full_document() first.")
           return
      
       print("\n" + "="*80)
       print("PDF ANALYSIS SUMMARY")
       print("="*80)
      
       for page in self.analysis_results["paginas"]:
           print(f"\nPAGE {page['pagina']}:")
           print(f"  Dimensions: {page['dimensiones']['ancho']} x {page['dimensiones']['alto']}")
           print(f"  Total lines: {len(page['lineas'])}")
           print(f"  Total tables: {len(page['tablas'])}")
          
           if page['tablas']:
               for idx, table in enumerate(page['tablas']):
                   print(f"  Table {idx + 1}: {table['num_rows']} rows x {table['num_columns']} columns")
          
           for i, line in enumerate(page['lineas'][:3]):
               print(f"  Line {line['numero_linea']}: '{line['texto_completo'][:50]}{'...' if len(line['texto_completo']) > 50 else ''}'")
               ubi = line['ubicacion_tabla']
               if ubi['ubicacion'] == 'dentro_tabla':
                   print(f"    -> In table {ubi['tabla_id']}, row {ubi['fila'] + 1}, col {ubi['columna'] + 1}")
               else:
                   print(f"    -> Free text (outside tables)")
          
           if len(page['lineas']) > 3:
               print(f"  ... and {len(page['lineas']) - 3} more lines")
  
   def get_statistics(self):
       """Obtains general document statistics."""
       if not self.analysis_results:
           return None
      
       stats = {
           "total_paginas": self.analysis_results["total_paginas"],
           "total_lineas": 0,
           "total_tablas": 0,
           "lineas_en_tablas": 0,
           "lineas_libres": 0,
           "fuentes_usadas": set(),
           "tamaños_fuente": [],
           "palabras_totales": 0
       }
      
       for page in self.analysis_results["paginas"]:
           stats["total_lineas"] += len(page["lineas"])
           stats["total_tablas"] += len(page["tablas"])
          
           for line in page["lineas"]:
               if line["ubicacion_tabla"]["ubicacion"] == "dentro_tabla":
                   stats["lineas_en_tablas"] += 1
               else:
                   stats["lineas_libres"] += 1
              
               stats["fuentes_usadas"].add(line["formato_principal"]["fuente"])
               stats["tamaños_fuente"].append(line["formato_principal"]["tamaño"])
               stats["palabras_totales"] += line["metadatos"]["num_palabras"]
      
       stats["fuentes_usadas"] = list(stats["fuentes_usadas"])
       stats["tamaño_fuente_promedio"] = round(
           sum(stats["tamaños_fuente"]) / len(stats["tamaños_fuente"]), 2
       ) if stats["tamaños_fuente"] else 0
      
       return stats
  
   def export_tables_to_csv(self, output_dir="tables_export"):
       """Exports all detected tables to separate CSV files."""
       if not self.analysis_results:
           print("No analysis available.")
           return
      
       os.makedirs(output_dir, exist_ok=True)
       table_count = 0
      
       for page in self.analysis_results["paginas"]:
           for table_idx, table in enumerate(page["tablas"]):
               table_count += 1
               filename = f"table_page{page['pagina']}_num{table_idx + 1}.csv"
               filepath = os.path.join(output_dir, filename)
              
               with open(filepath, 'w', encoding='utf-8', newline='') as f:
                   writer = csv.writer(f)
                  
                   for row in table["cells"]:
                       writer.writerow([cell["text"] for cell in row])
              
               print(f"Table exported: {filepath}")
      
       print(f"\nTotal exported tables: {table_count}")
  
   def filter_lines_by_criteria(self, **criteria):
       """
       Filters lines according to specific criteria.
       """
       if not self.analysis_results:
           return []
      
       filtered_lines = []
      
       for page in self.analysis_results["paginas"]:
           for line in page["lineas"]:
               match = True
              
               if "es_titulo" in criteria:
                   if line["metadatos"]["es_titulo"] != criteria["es_titulo"]:
                       match = False
              
               if "en_tabla" in criteria:
                   in_table = line["ubicacion_tabla"]["ubicacion"] == "dentro_tabla"
                   if in_table != criteria["en_tabla"]:
                       match = False
              
               if "fuente" in criteria:
                   if criteria["fuente"] not in line["formato_principal"]["fuente"]:
                       match = False
              
               if "tamaño_min" in criteria:
                   if line["formato_principal"]["tamaño"] < criteria["tamaño_min"]:
                       match = False
              
               if "tamaño_max" in criteria:
                   if line["formato_principal"]["tamaño"] > criteria["tamaño_max"]:
                       match = False
              
               if "contiene_texto" in criteria:
                   if criteria["contiene_texto"].lower() not in line["texto_completo"].lower():
                       match = False
              
               if match:
                   filtered_lines.append({
                       "pagina": page["pagina"],
                       **line
                   })
      
       return filtered_lines
  
   def close(self):
       """Closes the PDF document."""
       self.doc.close()
