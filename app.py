from gevent import monkey
monkey.patch_all()

import os
import time

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import src.backend.email_check as email_worker
from src.backend.statistics import statistics_store

app = Flask(__name__, template_folder="src/frontend/templates", static_folder="src/frontend/static")
cors_origins = os.getenv("SOCKETIO_CORS_ORIGINS")
socketio = SocketIO(app, cors_allowed_origins=cors_origins if cors_origins else None)

@app.route('/')
def index():
    return render_template('index.html')


@socketio.on("connect")
def send_initial_statistics(auth=None):
    emit("statistics_update", statistics_store.get_today().to_dict())


def process_email(socketio):
    while True:
        try:
            email_worker.check_email(socketio)
        except Exception as e:
            socketio.emit('error', {'message': str(e)})
        time.sleep(30)


if __name__ == '__main__':
    socketio.start_background_task(target=process_email, socketio=socketio)
    socketio.run(app, host='0.0.0.0', port=8000)
