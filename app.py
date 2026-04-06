#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template
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
socketio = SocketIO(app, cors_allowed_origins="*")

monitor_running = True
chain_status = {} # {'stage': 'status', 'message': ''}

def check_email():
    print("Checking email..")
    try:
        
        shutil.rmtree('scripts/input_data')
        
        os.mkdir('scripts/input_data')
        
        with open('scripts/login.json', 'r') as login_file:
            login_data = json.load(login_file)

        mail_pass = login_data['password']
        username = f"{login_data['username']}@uktaif.ru"
        imap_server = "ukexch.uktaif.ru"
        imap = imaplib.IMAP4_SSL(imap_server)
        imap.login(username, mail_pass)

        print("login_success")

        imap.select('INBOX')
        print("inbox selected")
        result, data = imap.search(None, 'UNSEEN')

        for num in data[0].split():
            print(data)
            _, msg_data = imap.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])

            socketio.emit('new_email', {'subject': base64.b64decode(msg['subject'][10:2]).decode('utf-8'), 'sender': msg['from']})
            

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

                    filePath = os.path.join('./scripts/input_data', fileName)
                    if not os.path.isfile(filePath):
                        print(fileName)
                        fp = open(filePath, 'wb')
                        fp.write(part.get_payload(decode=True))
                        fp.close()
                        print('fp closed ...')
 
                    with open('scripts/filename.txt', 'w') as filename_txt:
                        filename_txt.write(fileName)

           
            run_chain()

        imap.close()
        imap.logout()
    except Exception as e:
        print("Error!!!: ", e)
        socketio.emit('error', str(e))

def run_chain():
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
            
            if (script == 'pdf_parse.py'):
                socketio.emit('text_parse_started', 'true')
            elif (script == 'ai_output_json.py'):
                socketio.emit('ai_data_recognition_started')
            elif (script == 'directum.py', 'true'):
                socketio.emit('directum_api_started', 'true')
                
                


            cmd = ['python', f'{script}']
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='scripts/')
            
            chain_status['status'] = 'Completed' if result.returncode == 0 else 'Error'
            print(f"Stage completed - {name}")
            chain_status['log'] = result.stdout + result.stderr
            socketio.emit('chain_update', chain_status)
            time.sleep(1)

            if (script == 'pdf_parse.py'):
                socketio.emit('text_parse_finished', 'true')
            elif (script == 'ai_output_json.py'):
                socketio.emit('ai_data_recognition_finished')
            elif (script == 'directum.py', 'true'):
                socketio.emit('directum_api_finished', 'true')
             

        chain_status['complete'] = True
        socketio.emit('chain_complete')

    threading.Thread(target=execute_stage, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_monitor')
def start_monitor():
    global monitor_running
    monitor_running = True
    
#    scheduler = BackgroundScheduler()
 #   scheduler.add_job(check_email, 'interval', minutes=5)  # N минут
  #  scheduler.start()
    
    check_email()

    return {'status': 'started'}

@app.route('/stop_monitor') 
def stop_monitor():
    global monitor_running
    monitor_running = False
    socketio.emit('monitor_stopped')
    return {'status': 'stopped'}

if __name__ == '__main__':
    os.makedirs('results', exist_ok=True)
    app.run(host='127.0.0.1')
