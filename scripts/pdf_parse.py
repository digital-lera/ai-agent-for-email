import pdfplumber

with pdfplumber.open("input_data/file.pdf") as pdf, open("input_data/email.txt", "w", encoding="utf-8") as f:

    for page in pdf.pages:
        t = page.extract_text()
        if t:
            f.write(t + '\n')
print("")

