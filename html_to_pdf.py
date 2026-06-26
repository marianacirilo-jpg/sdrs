#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import fitz  # PyMuPDF
import json

def html_to_pdf(html_path, pdf_path):
    """Converte um arquivo HTML para PDF usando PyMuPDF"""
    try:
        # Abrir o arquivo HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Criar um documento PDF em branco
        doc = fitz.open()
        
        # Criar uma página
        page = doc.new_page(width=595, height=842)  # A4: 210mm x 297mm
        
        # Inserir o conteúdo HTML como texto (simplificado)
        # PyMuPDF não renderiza HTML diretamente, então faremos uma versão simplificada
        page.insert_text((50, 50), html_content[:4000] + "...", fontsize=10, rotate=0)
        
        # Salvar o PDF
        doc.save(pdf_path)
        doc.close()
        
        print(f"PDF criado: {pdf_path}")
        return True
    except Exception as e:
        print(f"Erro ao converter HTML para PDF: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 html_to_pdf.py <html_path> <pdf_path>")
        sys.exit(1)
    
    html_path = sys.argv[1]
    pdf_path = sys.argv[2]
    
    if not os.path.exists(html_path):
        print(f"Arquivo HTML não encontrado: {html_path}")
        sys.exit(1)
    
    success = html_to_pdf(html_path, pdf_path)
    sys.exit(0 if success else 1)