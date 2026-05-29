#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import threading
import subprocess
import imaplib
import email
from email.header import decode_header
import os
import shutil
import json
import time
import base64
import re

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", threaded=True)

monitor_running = True
chain_status = {}  # {'stage': 'status', 'message': ''}
email_found = False

def check_email():
    global email_found
    print("Checking email..")
    email_found = False
    
    try:
        shutil.rmtree('src/scripts/input_data')
        os.mkdir('src/scripts/input_data')
        
        with open('src/scripts/login.json', 'r') as login_file:
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
            check_email()
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

                        filePath = os.path.join('./src/scripts/input_data', fileName)
                        if not os.path.isfile(filePath):
                            print(fileName)
                            fp = open(filePath, 'wb')
                            fp.write(part.get_payload(decode=True))
                            fp.close()
                            print('fp closed ...')

                        with open('src/scripts/filename.txt', 'w') as filename_txt:
                            filename_txt.write(fileName)
                            socketio.emit('filename_recognized', f'{fileName}')
            
            imap.close()
            imap.logout()
            
            if email_found:
                run_chain()
            
    except Exception as e:
        print("Error!!!: ", e)
        socketio.emit('error', str(e))
        imap.close()
        imap.logout()

def run_chain():
    global email_found
    print("running stages")
    stages = [
        ('pdf_parse.py', 'Получение текста документа'),
        ('ai_output_json.py', 'Выделение необходимых данных'),
        ('directum.py', 'Создание входящего письма в Directum RX')
    ]

    def execute_stage():
        global chain_status
        for script, name in stages:
            chain_status['stage'] = name
            chain_status['status'] = 'Running...'
            socketio.emit('chain_update', chain_status)
            
            if script == 'pdf_parse.py':
                socketio.emit('text_parse_started', 'true')
            elif script == 'ai_output_json.py':
                socketio.emit('ai_data_recognition_started')
            elif script == 'directum.py':
                socketio.emit('directum_api_started', 'true')

            cmd = ['python', script]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='src/scripts/')
            
            chain_status['status'] = 'Completed' if result.returncode == 0 else 'Error'

            if chain_status['status'] == 'Error':
                socketio.emit('error')
                break

            print(f"Stage completed - {name}")
            chain_status['log'] = result.stdout + result.stderr
            socketio.emit('chain_update', chain_status)

            if script == 'pdf_parse.py':
                socketio.emit('text_parse_finished', 'true')
            elif script == 'ai_output_json.py':
                socketio.emit('ai_data_recognition_finished')
            elif script == 'directum.py':
                socketio.emit('directum_api_finished', 'true')

        chain_status['complete'] = True
        socketio.emit('chain_complete')
        
        # Wait 10s after chain finishes, then emit reset
        time.sleep(10)
        socketio.emit('reset')
        email_found = False

    execute_stage()

@app.get("/health")
def health():
    return jsonify(status="ok"), 200

@app.route('/')
def index():
    return render_template('index.html')
        
    
if __name__ == '__main__':
    os.makedirs('results', exist_ok=True)
    
    # Start Flask in background thread
    def run_flask():
        app.run(host='127.0.0.1', port=5000, use_reloader=False, threaded=True)
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Start email checker loop in main thread
    check_email()