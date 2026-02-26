"""Tests for the KVR Database Server."""

import pytest
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as server
from app import app, init_db


TEST_API_KEY = "test-secret-key"
HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def client(tmp_path):
    """Create a test client backed by a fresh in-memory-style temp database."""
    db_path = str(tmp_path / "test.db")
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    server.API_KEY = TEST_API_KEY

    with app.app_context():
        init_db()

    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_missing_api_key_returns_401(client):
    resp = client.get("/users/alice")
    assert resp.status_code == 401


def test_wrong_api_key_returns_401(client):
    resp = client.get("/users/alice", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

def test_create_user(client):
    resp = client.post(
        "/users",
        json={"username": "alice", "pin": 1234},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["pin"] == 1234
    assert data["kvrcoin"] == 0
    assert data["chess_points"] == 0


def test_create_user_with_all_fields(client):
    resp = client.post(
        "/users",
        json={"username": "bob", "pin": 5678, "kvrcoin": 100, "chess_points": 50},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["kvrcoin"] == 100
    assert data["chess_points"] == 50


def test_create_user_missing_username_returns_400(client):
    resp = client.post("/users", json={"pin": 1111}, headers=HEADERS)
    assert resp.status_code == 400


def test_create_user_missing_pin_returns_400(client):
    resp = client.post("/users", json={"username": "carol"}, headers=HEADERS)
    assert resp.status_code == 400


def test_create_user_duplicate_username_returns_409(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.post("/users", json={"username": "alice", "pin": 9999}, headers=HEADERS)
    assert resp.status_code == 409


def test_create_user_duplicate_pin_returns_409(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.post("/users", json={"username": "dave", "pin": 1234}, headers=HEADERS)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Get by username
# ---------------------------------------------------------------------------

def test_get_user_by_username(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.get("/users/alice", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "alice"


def test_get_nonexistent_user_returns_404(client):
    resp = client.get("/users/nobody", headers=HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get by PIN
# ---------------------------------------------------------------------------

def test_get_user_by_pin(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.get("/users/pin/1234", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "alice"


def test_get_nonexistent_pin_returns_404(client):
    resp = client.get("/users/pin/9999", headers=HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update user
# ---------------------------------------------------------------------------

def test_update_user(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.patch(
        "/users/alice",
        json={"kvrcoin": 500, "chess_points": 10},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["kvrcoin"] == 500
    assert data["chess_points"] == 10


def test_update_nonexistent_user_returns_404(client):
    resp = client.patch(
        "/users/nobody", json={"kvrcoin": 10}, headers=HEADERS
    )
    assert resp.status_code == 404


def test_update_with_no_valid_fields_returns_400(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.patch("/users/alice", json={"id": 99}, headers=HEADERS)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete user
# ---------------------------------------------------------------------------

def test_delete_user(client):
    client.post("/users", json={"username": "alice", "pin": 1234}, headers=HEADERS)
    resp = client.delete("/users/alice", headers=HEADERS)
    assert resp.status_code == 200
    # Confirm gone
    assert client.get("/users/alice", headers=HEADERS).status_code == 404


def test_delete_nonexistent_user_returns_404(client):
    resp = client.delete("/users/nobody", headers=HEADERS)
    assert resp.status_code == 404
