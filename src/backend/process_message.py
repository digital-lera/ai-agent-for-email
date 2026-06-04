import subprocess
import time


chain_status = {}  

def run_chain(socketio):
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
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='../scripts')
            
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