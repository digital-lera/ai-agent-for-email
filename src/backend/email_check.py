from pathlib import Path
import shutil
import os
import json
import re
import time

import imaplib
import base64
import email

import src.backend.process_message as process_message
import src.scripts.send_error_task as send_error_task

email_found = False

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
input_data_dir = scripts_dir / "input_data"

def check_email(socketio):
    global email_found
    print(f"Проверка почты...")
    email_found = False

    with open(scripts_dir / 'login.json', 'r') as login_file:
            login_data = json.load(login_file)

    mail_pass = f"{login_data['email-password']}"
    username = f"{login_data['username']}"
    imap_server = "ukexch.uktaif.ru"
    imap = imaplib.IMAP4_SSL(imap_server)

    global subject 
    global sender 


    try:

        imap.login(username, mail_pass)
        if input_data_dir.exists():
            shutil.rmtree(input_data_dir)

        os.mkdir(input_data_dir)
        

        imap.select('INBOX')
        result, data = imap.search(None, 'UNSEEN')

        unread_count = len(data[0].split())
        
        if unread_count == 0:

            time_interval_no_email = 30
            print(f"Непрочитанные сообщения не найдены. Повторная проверка через {time_interval_no_email} секунд")
            imap.close()
            imap.logout()
    
            time.sleep(time_interval_no_email)
            check_email(socketio)
        else:
            for num in data[0].split():
                email_found = True
                _, msg_data = imap.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                has_attachments = False

                socketio.emit('new_email', {
                    'subject': base64.b64decode(msg['subject'][10:2]).decode('utf-8'),
                    'sender': msg['from']
                })

                subject = base64.b64decode(msg['subject'][10:2]).decode('utf-8')
                sender = msg['from']

                print("Найдено непрочитанное входящее письмо.")

                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                        
                    
                    fileName = part.get_filename()
                    if fileName:
                        print(f"Найдено вложение: {fileName}")
                        has_attachments = True
                        parts = re.findall(r'\?B\?([A-Za-z0-9+/=]+)\?\=', fileName)

                        decoded_parts = []
                        for part_to_decode in parts:
                            bytes_data = base64.b64decode(part_to_decode)
                            text = bytes_data.decode('utf-8')
                            decoded_parts.append(text)

                        fileName = ' '.join(decoded_parts)
                        
                        if fileName == "":
                            fileName = "file.pdf"

                        filePath = os.path.join(input_data_dir, fileName)
                        if not os.path.isfile(filePath):
                            print(fileName)
                            fp = open(filePath, 'wb')
                            fp.write(part.get_payload(decode=True))
                            fp.close()

                        with open(scripts_dir / 'filename.txt', 'w') as filename_txt:
                            filename_txt.write(fileName)
                            socketio.emit('filename_recognized', f'{fileName}')
                    else: #обработка без вложений
                        plain_text = ""
                        plain_text += part.get_payload(decode=True)

                        with open(input_data_dir / "email.txt", "w") as file:
                            file.write(plain_text)    
            
            if email_found:
                process_message.run_chain(socketio, with_attachment=has_attachments)
            
    except Exception as e:
        print("При обработке почты возникла ошибка: ", e)
        socketio.emit('error', str(e))
        time_interval_error = 10
        imap.close()
        imap.logout()

        send_error_task.create_error_task(subject, sender)

        socketio.emit('reset')
        time.sleep(time_interval_no_email)
        check_email(socketio)
