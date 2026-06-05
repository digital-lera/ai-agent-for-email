from pathlib import Path
import subprocess
import time
import json

from src.scripts.pdf_parse import pdf_parse as pdf_parse
from src.scripts.ai_output_json import process_text_with_ai as process_text_with_ai
from src.scripts.directum import directum as directum

chain_status = {}  

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"

def run_chain(socketio):
    print("Запущена обработка письма.")
    stages = [
        ('pdf_parse.py', 'Получение текста документа'),
        ('ai_output_json.py', 'Выделение необходимых данных'),
        ('directum.py', 'Создание входящего письма в Directum RX')
    ]

    def execute_stage():
        global chain_status
        for script, name in stages:

            print(f"Текущая операция: {name}")

            chain_status['stage'] = name
            chain_status['status'] = 'В процессе'
            socketio.emit('chain_update', chain_status)
            
            try:
                if script == 'pdf_parse.py':
                    socketio.emit('text_parse_started', 'true')
                    pdf_parse()
                elif script == 'ai_output_json.py':
                    socketio.emit('ai_data_recognition_started')
                    process_text_with_ai()

                    try:
                        with open(scripts_dir / "processed_data.json", "r") as file:
                            json_data = json.load(file)

                        socketio.emit("json_data_recieved", json_data)
                    except:
                        print("Данные не были выделены")

                elif script == 'directum.py':
                    socketio.emit('directum_api_started', 'true')
                    directum()

                chain_status['status'] = 'Завершено'
            except Exception as e:
                chain_status['status'] = 'Error'

            # cmd = ['python', script]
            # result = subprocess.run(cmd, capture_output=True, text=True, cwd=scripts_dir)

            if chain_status['status'] == 'Error':
                socketio.emit('error')
                break

            print(f"Процесс завершен - {name}")
            chain_status['log'] = f"Процесс завершен - {name}"
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