import pytest

def pytest_addoption(parser): 
    parser.addoption("--username", action="store", default="def")
    parser.addoption("--password", action="store", default="def")
    parser.addoption("--url", action="store", default="def")