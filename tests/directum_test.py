import pytest 
import json
import warnings
import requests

def get_metadata_status_code(): 
    
    with open("src/scripts/login.json", "r") as file:
        auth_data = json.load(file)

    DIRECTUM_URL = f"{auth_data['odataurl']}"

    AUTH = (f"{auth_data['username']}", f"{auth_data['password']}")

    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    metadata_response = requests.get(
        f"{DIRECTUM_URL}/$metadata')",
        auth=AUTH,
        verify=False,
    )

    return metadata_response.status_code

def test_Directum_login():
    assert get_metadata_status_code() not in [401, 404]