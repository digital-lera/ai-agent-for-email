import asyncio
import base64
import email
import imaplib
import json
import os
import re
import shutil
from email.header import decode_header

import socketio
from flask_socketio import SocketIO
from flask import Flask, render_template, jsonify
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

api = FastAPI()
app = Flask(__name__)
sio = SocketIO(app, cors_allowed_origins="*", threaded=True)

templates = Jinja2Templates(directory="templates")

chain_status = {}
monitor_started = False


def safe_logout(imap):
    try:
        imap.close()
    except Exception:
        pass
    try:
        imap.logout()
    except Exception:
        pass


def decode_subject(msg):
    subject = msg.get("subject", "")
    parts = decode_header(subject)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(part)
    return "".join(out).strip()


def save_attachment(part):
    file_name = part.get_filename() or "file.pdf"

    parts = re.findall(r"\?B\?([A-Za-z0-9+/=]+)\?=", file_name)
    if parts:
        decoded_parts = []
        for p in parts:
            decoded_parts.append(base64.b64decode(p).decode("utf-8", errors="ignore"))
        file_name = " ".join(decoded_parts).strip() or "file.pdf"

    input_dir = "src/scripts/input_data"
    os.makedirs(input_dir, exist_ok=True)
    file_path = os.path.join(input_dir, file_name)

    with open(file_path, "wb") as fp:
        fp.write(part.get_payload(decode=True))

    return file_name


async def run_script(script_name):
    proc = await asyncio.create_subprocess_exec(
        "python",
        script_name,
        cwd="src/scripts",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


async def run_chain():
    global chain_status

    stages = [
        ("pdf_parse.py", "Получение текста документа", "text_parse_started", "text_parse_finished"),
        ("ai_output_json.py", "Выделение необходимых данных", "ai_data_recognition_started", "ai_data_recognition_finished"),
        ("directum.py", "Создание входящего письма в Directum RX", "directum_api_started", "directum_api_finished"),
    ]

    for script, name, started_event, finished_event in stages:
        chain_status["stage"] = name
        chain_status["status"] = "Running..."
        await sio.emit("chain_update", chain_status)
        await sio.emit(started_event, True)

        code, out, err = await run_script(script)
        chain_status["status"] = "Completed" if code == 0 else "Error"
        chain_status["log"] = out + err
        await sio.emit("chain_update", chain_status)

        if code != 0:
            await sio.emit("error", f"{script} failed")
            return

        await sio.emit(finished_event, True)

    chain_status["complete"] = True
    await sio.emit("chain_complete")
    await asyncio.sleep(10)
    await sio.emit("reset")


async def check_email_once():
    def sync_job():
        imap = None
        try:
            shutil.rmtree("src/scripts/input_data", ignore_errors=True)
            os.makedirs("src/scripts/input_data", exist_ok=True)

            with open("src/scripts/login.json", "r", encoding="utf-8") as login_file:
                login_data = json.load(login_file)

            mail_pass = login_data["email-password"]
            username = f'{login_data["username"]}@uktaif.ru'
            imap_server = "ukexch.uktaif.ru"

            imap = imaplib.IMAP4_SSL(imap_server)
            imap.login(username, mail_pass)
            imap.select("INBOX")

            result, data = imap.search(None, "UNSEEN")
            if result != "OK":
                return []

            unread_ids = data[0].split()
            if not unread_ids:
                return []

            found = []
            for num in unread_ids:
                _, msg_data = imap.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                found.append(msg)

            return found
        finally:
            if imap is not None:
                safe_logout(imap)

    return await asyncio.to_thread(sync_job)


async def process_messages(messages):
    global chain_status

    for msg in messages:
        await sio.emit("new_email", {
            "subject": decode_subject(msg),
            "sender": msg.get("from", "")
        })

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get("Content-Disposition") is None:
                continue

            file_name = save_attachment(part)
            with open("src/scripts/filename.txt", "w", encoding="utf-8") as f:
                f.write(file_name)

            await sio.emit("filename_recognized", file_name)

    if messages:
        asyncio.create_task(run_chain())


async def email_monitor():
    while True:
        try:
            messages = await check_email_once()
            if messages:
                await process_messages(messages)
        except Exception as e:
            await sio.emit("error", str(e))

        await asyncio.sleep(30)


@api.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@api.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@sio.event
async def connect(sid, environ):
    global monitor_started
    if not monitor_started:
        monitor_started = True
        asyncio.create_task(email_monitor())


@sio.event
async def disconnect(sid):
    pass