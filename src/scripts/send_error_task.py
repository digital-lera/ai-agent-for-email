import requests
from pathlib import Path
import json
import warnings
from datetime import datetime, timedelta

def create_error_task(subject, sender):

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    with open(scripts_dir / "login.json", "r") as file:
        auth_data = json.load(file)

    DIRECTUM_URL = f"{auth_data['odataurl']}"

    AUTH = (f"{auth_data['username']}", f"{auth_data['password']}")

    ERROR_TASK_PERFORMER_ID = auth_data['performer_id']

    task_text = f"Последнее пришедшее письмо не было обработано. Требуется ручная обработка. Отправитель: {sender}, тема письма: {subject}. \nЗадачу можно отправить в решенные, это просто отладка системы."
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Return": "representation",
        
    }

    deadline_iso = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    request = requests.post(
        f"{DIRECTUM_URL}/Docflow/CreateSimpleTask",
        verify=False,
        auth=AUTH,
        headers=headers,
        json={
            "assignmentType": "Assignment",
            "deadline": deadline_iso,
            "subject": "Входящее письмо не было обработано агентом.",
            "importance": "Normal",
            "text": f"{task_text}",
            "performerIds": [ERROR_TASK_PERFORMER_ID],  
            "observerIds": [ERROR_TASK_PERFORMER_ID],  
            "documentIds": []
        },
    )

    print(request.status_code)
    print(request.content.decode('utf-8'))
    print("Письмо обработать не удалось ни на одном этапе. Направлена задача с ошибкой.")


if __name__ == "__main__":
    create_error_task("", "")