from pypdf import PdfReader
r = PdfReader('/docs/統計區分類系統資料標準2.0.pdf')
print('pages:', len(r.pages))
for i in range(min(20, len(r.pages))):
    t = r.pages[i].extract_text()
    if t:
        print(f'=== p{i+1} ===')
        print(t[:3000])
