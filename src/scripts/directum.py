import requests
from dateutil import parser
import json
import re
import warnings

with open('login.json','r') as file:
    auth_data = json.load(file)

DIRECTUM_URL = f"{auth_data['odataurl']}"

AUTH = (f"{auth_data['username']}",f"{auth_data['password']}")

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

with open('processed_data.json','r') as file:
    data = json.load(file)

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
else:
    print("Контакт подписанта не найден. Будет создана задача на добавление подписанта вручную.")

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
else:
    print("Контакт адресата не найден. Будет создана задача на добавление адресата вручную.")



doc_response = requests.post(
       f"{DIRECTUM_URL}/IIncomingLetters",
      json={
         "Name":f"{data['content']}",
         "Subject":f"{data['content']}",
         "Correspondent@odata.bind":f"{DIRECTUM_URL}/ICounterparties(1700)",
         "Dated":f"{parser.parse(data['dateFrom']).date()}",
         "InNumber":f"{data['number']}",
         "SignedBy@odata.bind":f"{DIRECTUM_URL}/IContacts({signedby_id})" if signedby_id != -1 else "",
         "Addressee@odata.bind":f"{DIRECTUM_URL}/IEmployee({contact_id})" if contact_id != -1 else "" 
      
     },
       auth=AUTH,

verify=False
)

print(doc_response)
