

def pdf_parse():

    try:
        from pdf2image import convert_from_path
        print(">>> После импорта pdf2image")
    except Exception as e:
        print(f"ERROR при импорте pdf2image: {e}")
        import traceback
        traceback.print_exc()
        raise

    filename = 'file.pdf'

    with open('filename.txt', 'r') as file:
        filename = file.read()

    print(f"Вложение {filename} прочитано")

    images = convert_from_path(f"input_data/{filename}")

    if not(images):
        print("Изображение вложения не найдено.")

    try:
        from paddleocr import PaddleOCR
    except Exception as e:
        import traceback
        traceback.print_exc()  # ← покажет полный traceback
        raise

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

        print("Текст успешно распознан")

    with open("input_data/email.txt", "w") as file:
        file.write('\n'.join(rec_texts))
