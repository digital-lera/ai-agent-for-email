import imaplib
import base64
import email
from email.header import decode_header
import re
import shutil
import os
import json
import time
from pathlib import Path

import src.backend.process_message as process_message
import src.scripts.send_error_task as send_error_task


scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
input_data_dir = scripts_dir / "input_data"


processed_folder = "Обработано ИИ"

def decode_mime_header(header_value):
    """Декодирует MIME-заголовки с попыткой нескольких кодировок"""
    if not header_value:
        return ""
    
    decoded_fragments = decode_header(header_value)
    result_text = ""
    
    for text_bytes, charset in decoded_fragments:
        if isinstance(text_bytes, bytes):
            if charset:
                encodings = [charset, 'utf-8', 'windows-1251', 'gbk', 'iso-8859-1', 'latin-1']
            else:
                encodings = ['utf-8', 'windows-1251', 'gbk', 'latin-1']
            
            for encoding in encodings:
                try:
                    result_text += text_bytes.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                result_text += text_bytes.decode('latin-1', errors='replace')
        else:
            result_text += text_bytes
    
    return result_text


def decode_filename_base64(fileName):
    """Декодирует имя файла с Base64 и несколькими кодировками"""
    parts = re.findall(r'\?B\?([A-Za-z0-9+/=]+)\?\=', fileName)
    
    if not parts:
        return fileName
    
    decoded_parts = []
    
    for part_to_decode in parts:
        bytes_data = base64.b64decode(part_to_decode)
        
        for encoding in ['utf-8', 'windows-1251', 'gbk', 'latin-1']:
            try:
                decoded_parts.append(bytes_data.decode(encoding))
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            decoded_parts.append(bytes_data.decode('latin-1'))
    
    return ' '.join(decoded_parts)


def read_email_text(msg):
    """Читает текст email-сообщения"""
    text_body = ""
    
    for part in msg.walk():
        content_type = part.get_content_type()
        
        if content_type in ('text/plain', 'text/html'):
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset()
                if charset:
                    encodings = [charset, 'utf-8', 'windows-1251', 'latin-1']
                else:
                    encodings = ['utf-8', 'windows-1251', 'latin-1']
                
                for encoding in encodings:
                    try:
                        text_body = payload.decode(encoding)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    text_body = payload.decode('latin-1', errors='replace')
    
    return text_body


def check_email(socketio):
    subject = ""
    sender = ""
    error_reason = ""
    
    print("Проверка почты...")
    
    # 1. Чтение login.json
    try:
        login_file_path = scripts_dir / 'login.json'
        
        for encoding in ['utf-8', 'windows-1251', 'latin-1']:
            try:
                with open(login_file_path, 'r', encoding=encoding) as login_file:
                    login_data = json.load(login_file)
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        else:
            error_reason = "Не удалось прочитать login.json"
            raise Exception(error_reason)
            
    except Exception as e:
        print(f"Ошибка при чтении login.json: {e}")
        socketio.emit('error', str(e))
        send_error_task.create_error_task(subject, sender, reason=error_reason or str(e))
        socketio.emit('reset')
        time.sleep(10)
        check_email(socketio)
        return
    
    mail_pass = login_data['email-password']
    username = login_data['username']
    imap_server = "ukexch.uktaif.ru"
    
    imap = imaplib.IMAP4_SSL(imap_server)
    
    try:
        imap.login(username, mail_pass)

        try:
            imap.create(processed_folder)
            print(f"Папка '{processed_folder}' создана или уже существует")
        except Exception as e:
            print(f"⚠️ Не удалось создать папку '{processed_folder}': {e}")
        
        # Очистка директории
        if input_data_dir.exists():
            shutil.rmtree(input_data_dir)
        os.mkdir(input_data_dir)
        
        imap.select('INBOX')
        result, data = imap.search(None, 'UNSEEN')
        
        unread_count = len(data[0].split())
        
        if unread_count == 0:
            print("Непрочитанные сообщения не найдены. Повторная проверка через 30 секунд")
            imap.close()
            imap.logout()
            time.sleep(30)
            check_email(socketio)
            return
        
        # Обработка всех непрочитанных писем
        for num in data[0].split():
            _, msg_data = imap.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Декодирование заголовков
            subject = decode_mime_header(msg.get('subject'))
            sender = decode_mime_header(msg.get('from'))
            
            print(f"Найдено письмо: {subject}")
            
            socketio.emit('new_email', {
                'subject': subject,
                'sender': sender
            })
            
            # === ЖЕЛЕЗНАЯ ЛОГИКА ===
            has_attachments = False
            pdf_files_list = []  # Список всех PDF файлов
            all_attachments_text = []  # Все тексты вложений
            
            # 2. Поиск и обработка всех вложений
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                
                fileName = part.get_filename()
                
                if fileName:
                    has_attachments = True
                    decoded_filename = decode_filename_base64(fileName)
                    
                    if decoded_filename == "":
                        decoded_filename = "file.pdf"
                    
                    print(f"Найдено вложение: {decoded_filename}")
                    
                    # Сохраняем вложение
                    filePath = os.path.join(input_data_dir, decoded_filename)
                    
                    if not os.path.isfile(filePath):
                        fp = open(filePath, 'wb')
                        fp.write(part.get_payload(decode=True))
                        fp.close()
                        print(f"Вложение сохранён: {filePath}")
                    
                    # Если это PDF — добавляем в список
                    if decoded_filename.lower().endswith('.pdf'):
                        pdf_files_list.append(decoded_filename)
                    
                    # Попытка прочитать текст из вложения (для txt, html и др.)
                    try:
                        attachment_payload = part.get_payload(decode=True)
                        if attachment_payload:
                            # Попытка нескольких кодировок
                            for encoding in ['utf-8', 'windows-1251', 'latin-1']:
                                try:
                                    attachment_text = attachment_payload.decode(encoding)
                                    all_attachments_text.append(attachment_text)
                                    break
                                except (UnicodeDecodeError, LookupError):
                                    continue
                            else:
                                all_attachments_text.append(attachment_payload.decode('latin-1', errors='replace'))
                    except Exception as e:
                        print(f"Не удалось прочитать текст из вложения {decoded_filename}: {e}")
                    
                    socketio.emit('filename_recognized', decoded_filename)
            
            # === Сохраняем ВСЕ PDF имена в filename.txt (каждое с новой строки) ===
            if pdf_files_list:
                with open(scripts_dir / 'filename.txt', 'w', encoding='utf-8') as filename_txt:
                    for pdf_filename in pdf_files_list:
                        filename_txt.write(pdf_filename + '\n')
                print(f"✅ Сохранено {len(pdf_files_list)} PDF файлов в filename.txt")
            
            # === Сохраняем ВСЕ тексты вложений в email.txt ===
            if all_attachments_text:
                combined_text = '\n\n'.join(all_attachments_text)
                with open(input_data_dir / "email.txt", "w", encoding='utf-8') as email_txt:
                    email_txt.write(combined_text)
                print(f"✅ Сохранён текст из {len(all_attachments_text)} вложений в email.txt")
            
            
            # === ДЕЙСТВИЕ: Если есть PDF(ы) - отправляем на обработку ===
            if pdf_files_list:
                print(f"✅ PDF(ы) найдены ({len(pdf_files_list)}): {pdf_files_list}")
                print("Отправляем на обработку по цепи...")
                process_message.run_chain(socketio, with_attachment=has_attachments)
                
                # === Перемещаем письмо в папку "Обработано ИИ" после успешной обработки ===
                print(f"Перемещаю письмо {num} в папку '{processed_folder}'...")
                try:
                    imap.copy(num, processed_folder)       # Копируем в "Обработано ИИ"
                    imap.store(num, '+FLAGS', '\\Deleted') # Удаляем из INBOX
                    imap.expunge()                          # Экспонируем изменения
                    
                    print(f"✅ Письмо {num} успешно перемещено в '{processed_folder}'")
                except Exception as e:
                    print(f"⚠️ Не удалось переместить письмо {num}: {e}")
        
        imap.close()
        imap.logout()
        
        print("Все письма обработаны. Повторная проверка через 30 секунд")
        time.sleep(30)
        check_email(socketio)
        
    except Exception as e:
        print(f"При обработке почты возникла ошибка: {e}")
        socketio.emit('error', str(e))
        
        imap.close()
        imap.logout()
        
        send_error_task.create_error_task(subject, sender, reason=error_reason or str(e))
        
        socketio.emit('reset')
        time.sleep(10)
        check_email(socketio)