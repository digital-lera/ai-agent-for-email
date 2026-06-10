import pytest 
import json
import warnings
import requests

@pytest.fixture(scope="session")
def username(pytestconfig):
    return pytestconfig.getoption("username")

@pytest.fixture(scope="session")
def password(pytestconfig):
    return pytestconfig.getoption("password")

@pytest.fixture(scope="session")
def url(pytestconfig):
    return pytestconfig.getoption("url")

def get_metadata_status_code(username, password, url_address): 

    AUTH = (username, password)
    ADDRESS = url_address

    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    metadata_response = requests.get(
        f"{ADDRESS}/$metadata')",
        auth=AUTH,
        verify=False,
    )

    return metadata_response.status_code

def test_Directum_login(username, password, url):
    assert get_metadata_status_code(username, password, url) not in [401, 404]