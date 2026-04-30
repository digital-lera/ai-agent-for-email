import requests
import sys
from dateutil import parser
import json
import re
import warnings
from datetime import datetime, timedelta

from fuzzywuzzy import process, fuzz


DIRECTUM_URL = "адрес сервера для доступа к Directum RX" 
AUTH = ("логин/пароль для доступа к серверу", "TODO: basic аутентификацию сменить") 

SIGNEDBY_ID = -1
CONTACT_ID = -1
COUNTERPARTY_ID = -1
RESULT_DOCUMENT_ID = -1

ERRORS = []
MAIN_REFINED_DATA = {"Ключевые данные":"Полученные после обработки "}

def main():

    global DIRECTUM_URL
    global AUTH

    global SIGNEDBY_ID
    global CONTACT_ID
    global COUNTERPARTY_ID
    global RESULT_DOCUMENT_ID

    global MAIN_REFINED_DATA

    with open("src/scripts/login.json", "r") as file:
        auth_data = json.load(file)

    DIRECTUM_URL = f"{auth_data['odataurl']}"

    AUTH = (f"{auth_data['username']}", f"{auth_data['password']}")

    # TODO: пока скрыты предупреждения о недействительных сертификатах
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    # Забираем из файла готовые данные, взятые из письма LLM-моделью
    with open("src/scripts/processed_data.json", "r") as file:
        MAIN_REFINED_DATA = json.load(file)

    SIGNEDBY_ID = get_signed_by_contact()
    CONTACT_ID = get_recipient()
    COUNTERPARTY_ID = get_contragent()

    RESULT_DOCUMENT_ID = create_incoming_letter()

    add_files_to_incoming_letter() 

    if len(ERRORS) > 0:
        create_simple_task(ERRORS, RESULT_DOCUMENT_ID)

def find_fuzzy_name(response_with_names, name_to_find, is_name = False):
    json_str = response_with_names.content.decode("utf-8")

    def get_surname_and_first_letter(text):
        match = re.match(r'^(\S+)\s+(\S)', text)
        return match.group(1) + " " + match.group(2) if match else ""

    if len(json_str) > 0:
        json_data = json.loads(json_str)
        counterlist = [data_unit["Name"] for data_unit in json_data["value"]]

        if is_name:
            best_match = process.extractOne(
                get_surname_and_first_letter(name_to_find), 
                [get_surname_and_first_letter(name) for name in counterlist], 
                scorer=fuzz.ratio)
        else:
            best_match = process.extractOne(
                name_to_find, 
                counterlist, 
                scorer=fuzz.ratio)
        if best_match:
            matched_username, score = best_match

            if score >= 80:
                matched_id = next(
                    data_unit["Id"]
                    for data_unit in json_data["value"]
                    if matched_username in data_unit["Name"]
                )
                return matched_id
    
    return -1

def create_simple_task(error_text, attachment_id):
    error_string = "\n".join(error_text)
    task_text = f"Данные из  письма (см. вложения) не были обработаны корректно. Система вернула следующие ошибки: \n{error_string} \n\nПроверьте письмо. Если оно не содержит вышеописанных ошибок, просьба связаться с разработчиками."
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
            "subject": "Входящее письмо обработано с ошибкой.",
            "importance": "Normal",
            "text": f"{task_text}",
            "performerIds": [3887],  # Array of longs
            "observerIds": [3887],  # Empty array
            "documentIds": [attachment_id],  # Empty array
        },
    )


def get_signed_by_contact():
    # Ищем подписанта: обрезаем строку так, чтобы в ней точно не было лишних символов
    string_to_find = re.sub(r"[^а-яёА-ЯЁ ]", "", MAIN_REFINED_DATA["signedBy"])
    doc_response_signedby = requests.get(
        f"{DIRECTUM_URL}/IContacts?$filter=contains(Name,'{string_to_find[0]}')",
        auth=AUTH,
        verify=False,
    )

    
    matched_id = -1
    
    if len(string_to_find) < 1:
        print("Имя адресата не найдено в письме")
    else:
        matched_id = find_fuzzy_name(doc_response_signedby, string_to_find, is_name=True)

    if matched_id < 1:
        print(
            "Контакт подписанта не найден. Будет создана задача на добавление подписанта вручную."
        )
        global ERRORS
        ERRORS.append(
            f"Контакт подписавшего под именем {string_to_find} не найден в контактах. Tребуется создать новый контакт."
        )
    return matched_id

def get_recipient():

    global CONTACT_ID

    # Ищем получателя письма
    string_to_find = re.sub(r"[^а-яёА-ЯЁ ]", "", MAIN_REFINED_DATA["recipient"])

    doc_response_contact = requests.get(
        f"{DIRECTUM_URL}/IEmployees?$filter=contains(Name,'{string_to_find[0]}')",
        auth=AUTH,
        verify=False,
    )

    matched_id = -1
    
    if len(string_to_find) < 1:
        print("Имя адресата не найдено в письме")
    else:
        matched_id = find_fuzzy_name(doc_response_contact, string_to_find, is_name=True)

    if matched_id < 1:
        print(
            "Адресат письма не найден среди сотрудников. Будет создана задача на добавление адресата вручную."
        )
        global ERRORS
        ERRORS.append(
            f"Адресат под именем {string_to_find} не найден среди сотрудников. Требуется перепроверить правильность указанного имени"
        )
    return matched_id

def get_contragent():
    # Ищем контрагента
    string_to_find = re.sub(r"[^а-яёА-ЯЁ ]", "", MAIN_REFINED_DATA["correspondent"])

    doc_response_contragent = requests.get(
        f"{DIRECTUM_URL}/ICounterparties?$filter=contains(Name,'{string_to_find[0]}')",
        auth=AUTH,
        verify=False,
    )

    matched_id = -1
    
    if len(string_to_find) < 1:
        print("Имя контрагента не найдено в письме")
    else:
        matched_id = find_fuzzy_name(doc_response_contragent, string_to_find)

    if matched_id < 1:
        print(
            "Обнаруженный контрагент не найден в списках. Будет создана задача на добавление контрагента вручную."
        )
        global ERRORS
        ERRORS.append(
            f"Контрагент под именем {string_to_find} не найден среди сотрудников. Требуется перепроверить правильность указанного имени"
        )
    return matched_id

def create_incoming_letter():

    
    # Создаем входящее письмо
    doc_response = requests.post(
        f"{DIRECTUM_URL}/IIncomingLetters",
        json={
            "Name": f"{MAIN_REFINED_DATA['content']}",
            "Subject": f"{MAIN_REFINED_DATA['content']}",
            "Correspondent@odata.bind": f"{DIRECTUM_URL}/ICounterparties({COUNTERPARTY_ID})",
            "Dated": f"{parser.parse(MAIN_REFINED_DATA['dateFrom']).date()}",
            "InNumber": f"{MAIN_REFINED_DATA['number']}",
            "SignedBy@odata.bind": (
                f"{DIRECTUM_URL}/IContacts({SIGNEDBY_ID})" if SIGNEDBY_ID != -1 else ""
            ),
            "Addressee@odata.bind": (
                f"{DIRECTUM_URL}/IEmployee({CONTACT_ID})" if CONTACT_ID != -1 else ""
            ),
        },
        auth=AUTH,
        verify=False,
    )

    if doc_response.status_code > 300:
        sys.exit(f"Документ не создан, ошибка {doc_response.status_code}")
        return -1
    else:
        return doc_response.json()["Id"]

def add_files_to_incoming_letter():

    with open("src/scripts/filename.txt", "r") as f:
            pdf_path = f.read()

    pdf_bytes = b""

    try:
        with open(f"src/scripts/input_data/{pdf_path}", "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
    except:
        print("Файл не найден. Ошибка в пути")

    headers = {"Return": "representation"}

    version_payload = {
        "Note": "Файл, приложенный к письму",
        "AssociatedApplication": {"Id": 3},  # Adjust per metadata
    }

    version_response = requests.post(
        f"{DIRECTUM_URL}/IIncomingLetters({RESULT_DOCUMENT_ID})/Versions",
        headers=headers,
        json=version_payload,
        auth=AUTH,
        verify=False,
    )

    if version_response.status_code < 300:
        new_version_data = version_response.json()
        version_id = new_version_data["Id"]
    else:
        sys.exit(f"Версия документа не создана, ошибка {version_response.status_code}")

    session = requests.Session()
    session.verify = False
    session.auth = AUTH

    stream_url = (
        f"{DIRECTUM_URL}/IIncomingLetters({RESULT_DOCUMENT_ID})/Versions({version_id})/Body/$value"
    )

    headers = {"Content-Type": "application/octet-stream", "Accept": "application/json"}
    response = session.put(stream_url, headers=headers, data=pdf_bytes)

    if response.status_code in [200, 204]:
        print("PDF документ успешно загружен")
    else:
        print(
            f"Документ не был загружен. Ошибка: {response.status_code} - {response.content.decode('utf-8')}"
        )


if __name__ == "__main__":
    main()
