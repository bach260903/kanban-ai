import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pdfplumber

pdf_path = r"D:\KLTN_24K3_TA,TT_A43180_A44212_A43160_Nguyễn Đình Khánh, Cao Trung Hiếu, Nguyễn Thanh Mai_AI Assistant_Nguyễn Thị Huyền Châu.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    for i, page in enumerate(pdf.pages):
        print(f'\n--- PAGE {i+1} ---')
        t = page.extract_text()
        if t:
            print(t)
