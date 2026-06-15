import pytest
import imaplib
import json

imap_server = "ukexch.uktaif.ru"

@pytest.fixture(scope="session")
def username(pytestconfig):
    return pytestconfig.getoption("username")

@pytest.fixture(scope="session")
def password(pytestconfig):
    return pytestconfig.getoption("password")

@pytest.fixture(scope="module")
def email_login(username, password):
    if username == "def" or password == "def":
        pytest.skip("Email integration credentials were not provided")

    if "@" not in username:
        username += "@uktaif.ru"
    imap = imaplib.IMAP4_SSL(imap_server)
    status, messages = imap.login(username, password)
        
    assert status == 'OK', f"Login failed: {messages}"
    
    yield imap  
    
    try:
        imap.logout()
    except imaplib.IMAP4.abort:
        pass  

def test_Outlook_login(email_login):
    status, folders = email_login.list()
    assert status == 'OK'
