from pathlib import Path
from pdf2image import convert_from_path
import cv2
from rapidocr_onnxruntime import RapidOCR

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
input_data_dir = scripts_dir / "input_data"

def pdf_parse():

    filename = 'file.pdf'

    try:
        with open(scripts_dir / 'filename.txt', 'r') as file:
            filename = file.read()
    except Exception as e:
        print('Ошибка: файл не найден, проверьте правильность путей')

    print(f"Вложение {filename} прочитано")

    images = convert_from_path(input_data_dir /filename )

    if not(images):
        print("Изображение вложения не найдено.")

    try: 

        for index, image in enumerate(images):
            image_path = input_data_dir / "file.png"
            image.save(image_path, 'PNG')
            
        ocr = RapidOCR()

        text = ""
        rec_texts = []

        for index, image in enumerate(images):
            
            results, elapse = ocr(image_path)

            if results:
                for item in results:
                    box, text, score = item
                    rec_texts += text

            print(f"Текст cо страницы {index + 1} успешно распознан")
    except Exception as e:
        print(f"Текст не распознан, {e}")

    with open(input_data_dir / "email.txt", "w") as file:
        file.write('\n'.join(rec_texts))

