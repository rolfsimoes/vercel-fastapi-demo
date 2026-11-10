# Tests of the app. Each expected answer is written by hand.
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_hello_with_no_name():
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Olá, mundo!"}


def test_hello_with_a_name():
    response = client.get("/api/hello", params={"name": "Ana"})
    assert response.json() == {"message": "Olá, Ana!"}


def test_average_that_passes():
    # (7 + 8 + 9) / 3 = 8.0
    response = client.post("/api/average", json={"grades": [7, 8, 9]})
    assert response.status_code == 200
    assert response.json() == {"average": 8.0, "passed": True}


def test_average_that_does_not_pass():
    # (5 + 6) / 2 = 5.5
    response = client.post("/api/average", json={"grades": [5, 6]})
    assert response.json() == {"average": 5.5, "passed": False}


def test_grade_out_of_range():
    response = client.post("/api/average", json={"grades": [7, 11]})
    assert response.status_code == 422


def test_empty_list():
    response = client.post("/api/average", json={"grades": []})
    assert response.status_code == 422


def test_docs_page():
    response = client.get("/api/docs")
    assert response.status_code == 200
