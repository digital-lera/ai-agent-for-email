import os
import threading
import time
from pathlib import Path

from pdf2image import convert_from_path
import easyocr

from src.backend.models import ProcessingError


DEFAULT_OCR_MODEL_STORAGE_DIR = "/root/.EasyOCR/model"


def pdf_parse(pdf_files, output_path, config=None):
    config = config or {}
    if not pdf_files:
        raise ProcessingError("No PDF attachments were provided for OCR")

    gpu = _config_bool(os.getenv("OCR_GPU", config.get("ocr_gpu", True)))
    workers = int(config.get("ocr_workers", 0))
    confidence = float(config.get("ocr_confidence", 0.5))
    dpi = int(config.get("ocr_dpi", 200))
    heartbeat_seconds = int(config.get("ocr_heartbeat_seconds", 15))
    model_storage_dir = str(
        os.getenv(
            "OCR_MODEL_STORAGE_DIR",
            config.get("ocr_model_storage_dir", DEFAULT_OCR_MODEL_STORAGE_DIR),
        )
    )
    Path(model_storage_dir).mkdir(parents=True, exist_ok=True)

    print(f"Начинаю парсинг {len(pdf_files)} PDF файлов", flush=True)
    print(
        "Настройки OCR: "
        f"gpu={gpu}, workers={workers}, confidence={confidence}, dpi={dpi}, "
        f"model_storage_dir={model_storage_dir}",
        flush=True,
    )
    easyocr_device = _configure_cuda(gpu)

    try:
        started = time.monotonic()
        print(
            f"Инициализация EasyOCR Reader на устройстве {easyocr_device}...",
            flush=True,
        )
        ocr = easyocr.Reader(
            ["ru"],
            gpu=easyocr_device,
            model_storage_directory=model_storage_dir,
            verbose=True,
        )
        print(
            f"EasyOCR Reader инициализирован за {time.monotonic() - started:.1f} сек.",
            flush=True,
        )
    except Exception as exc:
        raise ProcessingError(f"Failed to initialize OCR: {exc}") from exc

    all_texts = []

    for pdf_path in pdf_files:
        print(f"\n--- Парсинг PDF: {pdf_path.name} ---", flush=True)
        try:
            if not pdf_path.exists():
                raise ProcessingError(f"PDF file not found: {pdf_path.name}")

            conversion_started = time.monotonic()
            print(f"Конвертация PDF в изображения с DPI={dpi}...", flush=True)
            images = convert_from_path(str(pdf_path), dpi=dpi)
            print(
                f"Конвертировано в {len(images)} изображений "
                f"за {time.monotonic() - conversion_started:.1f} сек.",
                flush=True,
            )
            pdf_text = []

            for index, image in enumerate(images):
                if len(images) > 5 and index > 4 and index != len(images) - 1:
                    print(
                        f"Страница {index + 1}/{len(images)} пропущена "
                        "по правилу обработки больших документов.",
                        flush=True,
                    )
                    continue

                image_path = output_path.parent / (
                    f"{pdf_path.stem}_page_{index + 1}.png"
                )
                print(
                    f"Сохранение страницы {index + 1}/{len(images)} в "
                    f"{image_path.name}...",
                    flush=True,
                )
                image.save(image_path, "PNG")
                print(
                    f"Страница {index + 1}/{len(images)} сохранена: "
                    f"{image_path.name}, размер={image.width}x{image.height}",
                    flush=True,
                )
                print(
                    f"Начинается OCR страницы {index + 1}/{len(images)}. "
                    "Первый запуск может занять несколько минут.",
                    flush=True,
                )
                page_started = time.monotonic()
                results = _read_page_with_heartbeat(
                    ocr,
                    image_path,
                    workers=workers,
                    heartbeat_seconds=heartbeat_seconds,
                    page_number=index + 1,
                    total_pages=len(images),
                )
                print(
                    f"OCR страницы {index + 1}/{len(images)} завершен за "
                    f"{time.monotonic() - page_started:.1f} сек.; "
                    f"найдено фрагментов: {len(results)}",
                    flush=True,
                )
                for _, text, probability in results:
                    if probability > confidence:
                        pdf_text.append(text)
                        print(
                            f"Страница {index + 1}: текст: {text} | "
                            f"уверенность: {probability:.2f}",
                            flush=True,
                        )
                    else:
                        print(
                            f"Страница {index + 1}: фрагмент отклонен "
                            f"(уверенность {probability:.2f} < {confidence:.2f})",
                            flush=True,
                        )

            if pdf_text:
                all_texts.append(f"=== {pdf_path.name} ===\n" + "\n".join(pdf_text))
                print(
                    f"PDF {pdf_path.name}: принято фрагментов {len(pdf_text)}",
                    flush=True,
                )
            else:
                print(
                    f"PDF {pdf_path.name}: подходящий текст не распознан.",
                    flush=True,
                )
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
    print(
        f"Все тексты сохранены в {output_path} ({len(all_texts)} PDF файлов)",
        flush=True,
    )
    return all_texts


def _read_page_with_heartbeat(
    ocr,
    image_path,
    *,
    workers,
    heartbeat_seconds,
    page_number,
    total_pages,
):
    finished = threading.Event()

    def report_progress():
        while not finished.wait(heartbeat_seconds):
            print(
                f"OCR страницы {page_number}/{total_pages} все еще выполняется...",
                flush=True,
            )

    reporter = None
    if heartbeat_seconds > 0:
        reporter = threading.Thread(target=report_progress, daemon=True)
        reporter.start()

    try:
        return ocr.readtext(
            str(image_path),
            decoder="greedy",
            beamWidth=1,
            batch_size=1,
            workers=workers,
            detail=1,
            paragraph=False,
        )
    finally:
        finished.set()
        if reporter is not None:
            reporter.join(timeout=1)


def _config_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "cuda"}


def _configure_cuda(gpu_requested):
    try:
        import torch
    except ImportError as exc:
        raise ProcessingError(
            "PyTorch is not installed; EasyOCR GPU mode cannot start"
        ) from exc

    print(f"PyTorch version: {torch.__version__}", flush=True)
    print(f"PyTorch CUDA runtime: {torch.version.cuda}", flush=True)
    print(
        f"CUDA доступна для PyTorch: {torch.cuda.is_available()}",
        flush=True,
    )
    print(
        f"Количество CUDA-устройств: {torch.cuda.device_count()}",
        flush=True,
    )

    if not gpu_requested:
        print("OCR GPU явно отключен. Используется CPU.", flush=True)
        return "cpu"

    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise ProcessingError(
            "OCR настроен на GPU, но PyTorch не видит CUDA-устройство внутри "
            "контейнера. Проверьте NVIDIA Container Toolkit, GPU reservation "
            "для сервиса app и CUDA-enabled сборку PyTorch."
        )

    device_index = int(os.getenv("OCR_CUDA_DEVICE", "0"))
    if device_index < 0 or device_index >= torch.cuda.device_count():
        raise ProcessingError(
            f"OCR_CUDA_DEVICE={device_index} недоступен; обнаружено устройств: "
            f"{torch.cuda.device_count()}"
        )

    torch.cuda.set_device(device_index)
    properties = torch.cuda.get_device_properties(device_index)
    memory_gib = properties.total_memory / (1024 ** 3)
    print(
        f"Выбрано CUDA-устройство {device_index}: {properties.name}, "
        f"VRAM={memory_gib:.1f} GiB, "
        f"compute capability={properties.major}.{properties.minor}",
        flush=True,
    )
    print(
        f"cuDNN version: {torch.backends.cudnn.version()}",
        flush=True,
    )
    return f"cuda:{device_index}"
