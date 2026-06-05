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

email_found = False

def check_email(socketio):
    global email_found
    print("Checking email..")
    email_found = False
    
    

    input_data_dir = Path(__file__).resolve().parent.parent / "scripts" / "input_data"

    

    try:
        if input_data_dir.exists():
            shutil.rmtree(input_data_dir)

        os.mkdir('input_data_dir')
        
        with open('../scripts/login.json', 'r') as login_file:
            login_data = json.load(login_file)

        mail_pass = f"{login_data['email-password']}"
        username = f"{login_data['username']}@uktaif.ru"
        imap_server = "ukexch.uktaif.ru"
        imap = imaplib.IMAP4_SSL(imap_server)
        imap.login(username, mail_pass)

        print("login_success")
        imap.select('INBOX')
        print("inbox selected")
        result, data = imap.search(None, 'UNSEEN')

        unread_count = len(data[0].split())
        
        if unread_count == 0:
            print("No unread emails")
            imap.close()
            imap.logout()
            time_interval_no_email = 30
    
            time.sleep(time_interval_no_email)
            check_email(socketio)
        else:
            for num in data[0].split():
                email_found = True
                _, msg_data = imap.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                socketio.emit('new_email', {
                    'subject': base64.b64decode(msg['subject'][10:2]).decode('utf-8'),
                    'sender': msg['from']
                })

                print("Found an unread email")

                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    fileName = part.get_filename()
                    print('file names processed ...')

                    if bool(fileName):
                        parts = re.findall(r'\?B\?([A-Za-z0-9+/=]+)\?\=', fileName)

                        decoded_parts = []
                        for part_to_decode in parts:
                            bytes_data = base64.b64decode(part_to_decode)
                            text = bytes_data.decode('utf-8')
                            decoded_parts.append(text)

                        fileName = ' '.join(decoded_parts)
                        
                        if fileName == "":
                            fileName = "file.pdf"

                        filePath = os.path.join('input_data_dir', fileName)
                        if not os.path.isfile(filePath):
                            print(fileName)
                            fp = open(filePath, 'wb')
                            fp.write(part.get_payload(decode=True))
                            fp.close()
                            print('fp closed ...')

                        with open('../scripts/filename.txt', 'w') as filename_txt:
                            filename_txt.write(fileName)
                            socketio.emit('filename_recognized', f'{fileName}')
            
            imap.close()
            imap.logout()
            
            if email_found:
                process_message.run_chain(socketio)
            
    except Exception as e:
        print("Error!!!: ", e)
        socketio.emit('error', str(e))