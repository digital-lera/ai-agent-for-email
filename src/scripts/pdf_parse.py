from pdf2image import convert_from_path
import easyocr

from src.backend.models import ProcessingError


def pdf_parse(pdf_files, output_path):
    if not pdf_files:
        raise ProcessingError("No PDF attachments were provided for OCR")

    print(f"Начинаю парсинг {len(pdf_files)} PDF файлов")

    try:
        ocr = easyocr.Reader(["ru"])
    except Exception as exc:
        raise ProcessingError(f"Failed to initialize OCR: {exc}") from exc

    all_texts = []

    for pdf_path in pdf_files:
        print(f"\n--- Парсинг PDF: {pdf_path.name} ---")
        try:
            if not pdf_path.exists():
                raise ProcessingError(f"PDF file not found: {pdf_path.name}")

            images = convert_from_path(str(pdf_path))
            print(f"Конвертировано в {len(images)} изображений")
            pdf_text = []

            for index, image in enumerate(images):
                if len(images) > 5 and index > 4 and index != len(images) - 1:
                    continue

                results = ocr.readtext(image)
                for _, text, probability in results:
                    if probability > 0.5:
                        pdf_text.append(text)
                        print(
                            f"Page {index}: Text: {text} | "
                            f"Confidence: {probability:.2f}"
                        )

            if pdf_text:
                all_texts.append(f"=== {pdf_path.name} ===\n" + "\n".join(pdf_text))
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                f"Failed to parse PDF {pdf_path.name}: {exc}"
            ) from exc

    if not all_texts:
        raise ProcessingError("OCR did not recognize text in any PDF attachment")

    combined_text = "\n\n".join(all_texts)
    output_path.write_text(combined_text, encoding="utf-8")
    print(f"Все тексты сохранены в {output_path} ({len(all_texts)} PDF файлов)")
    return all_texts
