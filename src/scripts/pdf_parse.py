from pathlib import Path
from pdf2image import convert_from_path
import easyocr

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
input_data_dir = scripts_dir / "input_data"


def pdf_parse():

    filename = 'file.pdf'

    try:
        with open(scripts_dir / 'filename.txt', 'r') as file:
            filename = file.read()
    except Exception as e:
        print('Ошибка: файл не найден, проверьте правильность путей')


    try:
        images = convert_from_path(input_data_dir / filename)
    except Exception as e:
        print("Изображение вложения не найдено.")

    try: 

        for index, image in enumerate(images):
            image_path = input_data_dir / f"file_{index}.png"
            image.save(image_path , 'PNG')

        ocr =  easyocr.Reader(['ru'])

        text = ""
        rec_texts = []

        for index, image in enumerate(images):
            

            results = ocr.readtext(str(image_path))

            # Loop through and print the results
            for (bbox, text, prob) in results:
                print(f"Text: {text} | Confidence: {prob:.2f}")
                rec_texts += text

            print("Текст успешно распознан")

        with open(input_data_dir / "email.txt", "w") as file:
            file.write(' '.join(rec_texts))
            
    except Exception as e:
        print(f"Текст не распознан, {e}")
