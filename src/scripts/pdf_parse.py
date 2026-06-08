from pathlib import Path
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
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

    print(f"Вложение {filename} прочитано")

    try:
        images = convert_from_path(input_data_dir / "Вх. письмо от ООО _Вк Цифровые Технологии_ №ВХ_1495 от 14.05.2026 _О предложении рассмотрения_(600064v2)_removed.pdf")
    except Exception as e:
        print("Изображение вложения не найдено.")

    try: 

        for index, image in enumerate(images):
            image_path = input_data_dir / "file.png"
            image.save(image_path + f"_{index}", 'PNG')
            
        # ocr = PaddleOCR(
        #     lang='ru',
        #     use_doc_orientation_classify=False,
        #     use_doc_unwarping=False,
        #     use_textline_orientation=False
        #     )

        ocr =  easyocr.Reader(['ru'])

        text = ""
        rec_texts = []

        for index, image in enumerate(images):
            
            # result = ocr.predict(image_path)

            # if isinstance(result, list) and len(result) > 0:
            #     rec_texts += result[0].get("rec_texts", [])
            # elif isinstance(result, dict):
            #     rec_texts += result.get("rec_texts", [])
            # else:
            #     rec_texts += []

            results = ocr.readtext(str(image_path))

            # Loop through and print the results
            for (bbox, text, prob) in results:
                print(f"Text: {text} | Confidence: {prob:.2f}")
                rec_texts += text

            print("Текст успешно распознан")
    except Exception as e:
        print(f"Текст не распознан, {e}")

    with open(input_data_dir / "email.txt", "w") as file:
        file.write(''.join(rec_texts))


pdf_parse()