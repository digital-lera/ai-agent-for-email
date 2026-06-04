from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

import src.backend.email_check as email_worker

app = Flask(__name__, template_folder="src/frontend/templates", static_folder="src/frontend/static")
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.start_background_task(target=email_worker.check_email, socketio=socketio)