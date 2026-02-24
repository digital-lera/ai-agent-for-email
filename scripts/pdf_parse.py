from pdf2image import convert_from_path
import pytesseract
from PIL import Image

images = convert_from_path("scripts/input_data/file.pdf")

text = ""

for index, image in enumerate(images):
    image_path = "scripts/input_data/file.png"
    image.save(image_path, 'PNG')

        
    text += pytesseract.image_to_string(Image.open(image_path), lang='rus', config=r'--oem 3 --psm 6')

with open("email.txt", "w") as file:
    file.write(text)
