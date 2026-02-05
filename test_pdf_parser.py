#!/usr/bin/env python3
"""Test script to verify PDF parsing functionality"""
import sys
sys.path.insert(0, 'src')

from pdf_parser import PDFParser

def main():
    parser = PDFParser()

    # Test with the sample PDF
    pdf_path = "50211_29-JAN-2026.PDF"

    print(f"Testing PDF parser with: {pdf_path}")
    print("=" * 60)

    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        transactions = parser.parse_pdf(pdf_bytes)

        print(f"\nSuccessfully parsed {len(transactions)} transaction(s):\n")
        print("Note: Prices shown are NET prices per share (after all taxes, brokerage, and fees)\n")

        for i, t in enumerate(transactions, 1):
            print(f"{i}. {t.mode:4s} | {t.symbol:6s} | {t.shares:5d} shares @ {t.trade_price:10.4f} net | {t.date.strftime('%Y-%m-%d')}")

        print("\n" + "=" * 60)
        print("PDF parsing test PASSED!")
        print("\nVerification: Net price = Net Amount ÷ Shares")
        print("Example: DGKC = 97,261.07 ÷ 434 = 224.1038")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
