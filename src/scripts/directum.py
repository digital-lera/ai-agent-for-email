import requests
import sys
from dateutil import parser
import json
import re
import warnings
from datetime import datetime, timedelta

def create_simple_task(error_text, attachment_id):
    error_string = '\n'.join(error_text)
    task_text = f"Данные из  письма (см. вложения) не были обработаны корректно. Система вернула следующие ошибки: \n{error_string} \n\nПроверьте письмо. Если оно не содержит вышеописанных ошибок, просьба связаться с разработчиками."
    headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Return": "representation"
}   
    request = requests.post(
            f"{DIRECTUM_URL}/Docflow/CreateSimpleTask",
            verify=False,
            auth=AUTH,
            headers=headers,
            json={
                "assignmentType": "Assignment",
                "deadline": (datetime.now() + timedelta(days=1)).isoformat() + "Z",
                "subject": "Входящее письмо обработано с ошибкой.",
                "importance": "Normal",
                "text": f"{task_text}",
                "performerIds": [3887],  # Array of longs
                "observerIds": [3887],  # Empty array
                "documentIds": [attachment_id]  # Empty array

                }
            )

    #Открываем данные с логином, паролем и URL
with open('login.json','r') as file:
    auth_data = json.load(file)

DIRECTUM_URL = f"{auth_data['odataurl']}"

AUTH = (f"{auth_data['username']}",f"{auth_data['password']}")

#TODO: пока скрыты предупреждения о недействительных сертификатах
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


#Забираем из файла готовые данные, взятые из письма LLM-моделью
with open('processed_data.json','r') as file:
    data = json.load(file)

errors = []

#Ищем подписанта: обрезаем строку так, чтобы в ней точно не было лишних символов
string_to_find = re.sub(r'[^а-яёА-ЯЁ ]', '', data['signedBy'])
doc_response_signedby = requests.get(
        f"{DIRECTUM_URL}/IContacts?$filter=contains(Name,'{string_to_find}')",
        auth=AUTH,
        verify=False
        )
with open("output.txt","w") as f:
    f.write(doc_response_signedby.content.decode('utf-8'))

json_str=doc_response_signedby.content.decode('utf-8');
signedby_id = -1

if (len(json_str)>0):
    json_data=json.loads(json_str)
    signedby_id=json_data['value'][0]['Id']
elif len(string_to_find)<1:
    print("Имя подписанта не найдено в письме")
else:
    print("Контакт подписанта не найден. Будет создана задача на добавление подписанта вручную.")
    errors.append(f"Контакт подписавшего под именем {string_to_find} не найден в контактах. Возможно, требуется создать новый контакт.")

#Ищем получателя письма
string_to_find = re.sub(r'[^а-яёА-ЯЁ ]', '', data['recipient'])

doc_response_contact = requests.get(
        f"{DIRECTUM_URL}/IEmployees?$filter=contains(Name,'{string_to_find}')",
        auth=AUTH,
        verify=False
        )
with open("output.txt","w") as f:
    f.write(doc_response_contact.content.decode('utf-8'))

json_str=doc_response_contact.content.decode('utf-8');
contact_id = -1

if (len(json_str)>0):
    json_data=json.loads(json_str)
    contact_id=json_data['value'][0]['Id']
elif len(string_to_find)<1:
    print("Имя адресата не найдено в письме")
else:
    print("Адресат письма не найден среди сотрудников. Будет создана задача на добавление адресата вручную.")
    errors.append(f"Адресат под именем {string_to_find} не найден среди сотрудников. Требуется перепроверить правильность указанного имени")

with open("filename.txt", "r") as f:
    pdf_path = f.read()

pdf_bytes = b""

try:
    with open(f"input_data/{pdf_path}", "rb") as pdf_file:
        pdf_bytes = pdf_file.read()
except:
    print("Файл не найден. Ошибка в пути")

#Создаем входящее письмо
doc_response = requests.post(
    f"{DIRECTUM_URL}/IIncomingLetters",
    json={
        "Name":f"{data['content']}",
        "Subject":f"{data['content']}",
        "Correspondent@odata.bind":f"{DIRECTUM_URL}/ICounterparties(1700)",
        "Dated":f"{parser.parse(data['dateFrom']).date()}",
        "InNumber":f"{data['number']}",
        "SignedBy@odata.bind":f"{DIRECTUM_URL}/IContacts({signedby_id})" if signedby_id != -1 else "",
        "Addressee@odata.bind":f"{DIRECTUM_URL}/IEmployee({contact_id})" if contact_id != -1 else "",
    },
    auth=AUTH,

verify=False
)


if doc_response.status_code == 201:
    new_doc_data = doc_response.json()
    doc_id = new_doc_data["Id"]
else:
    sys.exit(f"Документ не создан, ошибка {doc_response.status_code}")


headers={
        "Return":"representation"
        }

version_payload = {
    "Note":"Файл, приложенный к письму",
    "AssociatedApplication": {"Id": 3},  # Adjust per metadata
}

version_response = requests.post(
    f"{DIRECTUM_URL}/IIncomingLetters({doc_id})/Versions",
    headers=headers,
    json=version_payload,
    auth=AUTH,
    verify=False
)

if version_response.status_code < 300:
    new_version_data = version_response.json()
    version_id = new_version_data["Id"]
else:
    sys.exit(f"Документ не создан, ошибка {version_response.status_code}")


stream_url = f"{DIRECTUM_URL}/IIncomingLetters({doc_id})/Versions({version_id})/Body/$value" 

headers = {
    "Content-Type": "application/octet-stream",
    "Accept": "application/json"
}

response = requests.put(
    stream_url,
    headers=headers,
        data=pdf_bytes,
    auth=AUTH,
    verify=False
)

if response.status_code in [200, 204]:
    print("PDF документ успешно загружен")
else:
    print(f"Документ не был загружен. Ошибка: {response.status_code} - {response.content.decode('utf-8')}")


if len(errors) > 0:
    create_simple_task(errors, doc_id);
