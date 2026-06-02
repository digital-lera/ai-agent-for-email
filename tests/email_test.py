import pytest
import imaplib
import json

with open("login.json", "r") as file:
        login_data = json.load(file)

mail_pass = f"{login_data['email-password']}"
username = f"{login_data['username']}@uktaif.ru"
imap_server = "ukexch.uktaif.ru"


@pytest.fixture(scope="module")
def email_login():

    
    imap = imaplib.IMAP4_SSL(imap_server)
    status, messages = imap.login(username, mail_pass)
        
    assert status == 'OK', f"Login failed: {messages}"
    
    yield imap  
    
    try:
        imap.logout()
    except imaplib.IMAP4.abort:
        pass  

def test_Outlook_login(email_login):
    status, folders = email_login.list()
    assert status == 'OK'