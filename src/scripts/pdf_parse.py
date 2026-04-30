from pdf2image import convert_from_path
from PIL import Image
from paddleocr import PaddleOCR

filename = 'file.pdf'

with open('filename.txt', 'r') as file:
    filename = file.read()


images = convert_from_path(f"input_data/{filename}")

if not(images):
    print("images_were_not_found")

print(f"{filename} is read")

ocr = PaddleOCR(
        lang='ru',
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
        )

text = ""
rec_texts = []

for index, image in enumerate(images):
    image_path = "input_data/file.png"
    image.save(image_path, 'PNG')
    
    result = ocr.predict(image_path)

    if isinstance(result, list) and len(result) > 0:
        rec_texts += result[0].get("rec_texts", [])
    elif isinstance(result, dict):
        rec_texts += result.get("rec_texts", [])
    else:
        rec_texts += []

    print("text recognized")

with open("input_data/email.txt", "w") as file:
    file.write('\n'.join(rec_texts))
