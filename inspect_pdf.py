#!/usr/bin/env python3
"""Inspect PDF structure to understand format"""
import sys
import pdfplumber

def main():
    pdf_path = "50211_29-JAN-2026.PDF"

    print(f"Inspecting PDF: {pdf_path}")
    print("=" * 80)

    with pdfplumber.open(pdf_path) as pdf:
        print(f"\nTotal pages: {len(pdf.pages)}")

        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\n{'='*80}")
            print(f"PAGE {page_num}")
            print('='*80)

            # Extract text
            text = page.extract_text()
            print("\n--- PAGE TEXT ---")
            print(text[:1000])  # First 1000 chars
            print("\n...")

            # Extract tables
            tables = page.extract_tables()
            print(f"\n--- TABLES ({len(tables)} found) ---")
            for i, table in enumerate(tables, 1):
                print(f"\nTable {i}:")
                if table:
                    print(f"  Rows: {len(table)}")
                    print(f"  Columns: {len(table[0]) if table else 0}")
                    print(f"  Header: {table[0] if table else None}")
                    if len(table) > 1:
                        print(f"  First data row: {table[1]}")

if __name__ == "__main__":
    main()
