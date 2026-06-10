import requests
from pathlib import Path
import json
from datetime import datetime, timedelta

def create_error_task():

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"

    with open(scripts_dir / "login.json", "r") as file:
        auth_data = json.load(file)
        print("логин получен")

    DIRECTUM_URL = f"{auth_data['odataurl']}"

    AUTH = (f"{auth_data['username']}", f"{auth_data['password']}")

    ERROR_TASK_PERFORMER_ID = auth_data['performer_id']

    task_text = f"Последнее пришедшее письмо не было обработано. Требуется ручная обработка."
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Return": "representation",
    }

    request = requests.post(
        f"{DIRECTUM_URL}/Docflow/CreateSimpleTask",
        verify=False,
        auth=AUTH,
        headers=headers,
        json={
            "assignmentType": "Assignment",
            "deadline": (datetime.now() + timedelta(days=1)).isoformat() + "Z",
            "subject": "Входящее письмо не было обработано агентом.",
            "importance": "Normal",
            "text": f"{task_text}",
            "performerIds": [ERROR_TASK_PERFORMER_ID],  
            "observerIds": [ERROR_TASK_PERFORMER_ID],  
        },
    )



    print(request.status_code)

if __name__ == "__main__":
    create_error_task()