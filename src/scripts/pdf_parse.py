from pathlib import Path
from pdf2image import convert_from_path
import easyocr


scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
input_data_dir = scripts_dir / "input_data"


def pdf_parse():
    """
    Парсит ВСЕ PDF файлы из input_data_dir:
    - Читает filename.txt (все имена с новой строки)
    - Для каждого PDF: конвертирует в изображения → OCR → собирает текст
    - Все тексты объединяет и сохраняет в email.txt
    """
    
    # 1. Чтение списка всех PDF файлов
    pdf_files = []
    
    try:
        with open(scripts_dir / 'filename.txt', 'r', encoding='utf-8') as file:
            content = file.read()
            pdf_files = [line.strip() for line in content.split('\n') if line.strip()]
    except Exception as e:
        print(f'Ошибка: файл filename.txt не найден или пуст, {e}')
        return
    
    if not pdf_files:
        print('Ошибка: в filename.txt нет PDF файлов')
        return
    
    print(f"Начинаю парсинг {len(pdf_files)} PDF файлов: {pdf_files}")
    
    # 2. OCR инициализация
    try:
        ocr = easyocr.Reader(['ru'])
    except Exception as e:
        print(f"Ошибка создания OCR reader: {e}")
        return
    
    # 3. Парсинг каждого PDF и сбор всех текстов
    all_texts = []
    
    for pdf_filename in pdf_files:
        print(f"\n--- Парсинг PDF: {pdf_filename} ---")
        
        try:
            pdf_path = input_data_dir / pdf_filename
            
            if not pdf_path.exists():
                print(f"PDF файл не найден: {pdf_path}")
                continue
            
            # Конвертация PDF в изображения
            images = convert_from_path(str(pdf_path))
            print(f"Конвертировано в {len(images)} изображений")
            
            # Сохранение изображений
            for index, image in enumerate(images):
                image_path = input_data_dir / f"{pdf_filename}_page_{index}.png"
                image.save(str(image_path), 'PNG')
            
            # OCR для каждого изображения
            pdf_text = []
            
            for index, image in enumerate(images):
                image_path = input_data_dir / f"{pdf_filename}_page_{index}.png"
                
                results = ocr.readtext(str(image_path))
                
                # Сбор текста с высоким confidence
                for (bbox, text, prob) in results:
                    if prob > 0.5:  # Только текст с confidence > 50%
                        pdf_text.append(text)
                        print(f"Page {index}: Text: {text} | Confidence: {prob:.2f}")
            
            if pdf_text:
                all_texts.append(f"=== {pdf_filename} ===\n" + '\n'.join(pdf_text))
                print(f"✅ Текст из {pdf_filename} распознан ({len(pdf_text)} фрагментов)")
            else:
                print(f"⚠️ Текст из {pdf_filename} не распознан")
                
        except Exception as e:
            print(f"Ошибка при парсинге PDF {pdf_filename}: {e}")
    
    # 4. Сохранение всех текстов в email.txt
    if all_texts:
        combined_text = '\n\n'.join(all_texts)
        
        with open(input_data_dir / "email.txt", "w", encoding='utf-8') as file:
            file.write(combined_text)
        
        print(f"\n✅ Все тексты сохранены в email.txt ({len(all_texts)} PDF файлов)")
        print(f"Общий размер: {len(combined_text)} символов")
    else:
        print("\n⚠️ Текст из всех PDF файлов не распознан")
    
    return all_texts