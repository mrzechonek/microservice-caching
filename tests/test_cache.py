from secrets import token_urlsafe

import pytest
import requests


@pytest.fixture
def email():
    return "test@user.com"


@pytest.fixture
def client(email):
    s = requests.Session()
    s.headers["x-user"] = email

    return s


@pytest.fixture
def email2():
    return "other@user.com"


@pytest.fixture
def client2(email2):
    s = requests.Session()
    s.headers["x-user"] = email2

    return s


@pytest.fixture(autouse=True)
def remove_all_lists(client):
    yield
    lists = client.get("http://localhost:8080/lists").json()
    for todo_list in lists:
        client.delete(f"http://localhost:8080/lists/{todo_list['list_id']}")


def test_todo_list_create(client, email):
    # warm-up the cache
    client.get("http://localhost:8080/lists")

    name = token_urlsafe(8)
    create_list = client.post(
        "http://localhost:8080/lists", json=dict(name=name)
    ).json()

    assert create_list["list_id"]
    assert create_list["name"] == name

    todo_list = client.get(
        f"http://localhost:8080/lists/{create_list['list_id']}"
    ).json()

    assert todo_list["list_id"] == create_list["list_id"]
    assert todo_list["name"] == name
    assert todo_list["collaborators"] == [email]
    assert todo_list["entries"] == []

    lists = client.get("http://localhost:8080/lists").json()
    assert lists == [dict(list_id=create_list["list_id"], name=name)]


@pytest.fixture
def list_id(client):
    name = token_urlsafe(8)
    create_list = client.post(
        "http://localhost:8080/lists", json=dict(name=name)
    ).json()
    return create_list["list_id"]


def test_entry_create(client, list_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/lists/{list_id}")
    client.get(f"http://localhost:8080/lists/{list_id}/entries")

    text = token_urlsafe(8)
    create_entry = client.post(
        f"http://localhost:8080/lists/{list_id}/entries", json=dict(text=text)
    ).json()

    assert create_entry["entry_id"]
    assert create_entry["text"] == text

    entry = client.get(
        f"http://localhost:8080/lists/{list_id}/entries/{create_entry['entry_id']}"
    ).json()
    assert entry["entry_id"] == create_entry["entry_id"]
    assert entry["text"] == text

    entries = client.get(f"http://localhost:8080/lists/{list_id}/entries").json()
    assert entries == [
        dict(
            entry_id=create_entry["entry_id"], text=text,
        )
    ]

    todo_list = client.get(f"http://localhost:8080/lists/{list_id}").json()
    assert todo_list["entries"] == [
        dict(
            entry_id=create_entry["entry_id"], text=text,
        )
    ]


@pytest.fixture
def entry_id(list_id, client):
    text = token_urlsafe(8)
    create_entry = client.post(
        f"http://localhost:8080/lists/{list_id}/entries", json=dict(text=text)
    ).json()
    return create_entry["entry_id"]


def test_entry_delete(client, list_id, entry_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/lists/{list_id}")
    client.get(f"http://localhost:8080/lists/{list_id}/entries")
    client.get(f"http://localhost:8080/lists/{list_id}/entries/{entry_id}")

    client.delete(f"http://localhost:8080/lists/{list_id}/entries/{entry_id}")

    entry_status = client.get(
        f"http://localhost:8080/lists/{list_id}/entries/{entry_id}"
    ).status_code
    assert entry_status == 404

    entries = client.get(f"http://localhost:8080/lists/{list_id}/entries").json()
    assert entries == []

    todo_list = client.get(f"http://localhost:8080/lists/{list_id}").json()
    assert todo_list["entries"] == []


def test_todo_list_delete(client, list_id, entry_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/lists/{list_id}")
    client.get(f"http://localhost:8080/lists/{list_id}/entries")
    client.get(f"http://localhost:8080/lists/{list_id}/entries/{entry_id}")
    client.get(f"http://localhost:8080/lists/{list_id}/entries/{entry_id}/nodes")

    client.delete(f"http://localhost:8080/lists/{list_id}")

    entry_status = client.get(
        f"http://localhost:8080/lists/{list_id}/entries/{entry_id}"
    ).status_code
    assert entry_status == 404

    entries_status = client.get(
        f"http://localhost:8080/lists/{list_id}/entries"
    ).status_code
    assert entries_status == 404

    todo_list_status = client.get(
        f"http://localhost:8080/lists/{list_id}"
    ).status_code
    assert todo_list_status == 404

    lists = client.get("http://localhost:8080/lists").json()
    assert lists == []


def test_collaborators(list_id, client, email, client2, email2):
    todo_list = client.get(f"http://localhost:8080/lists/{list_id}").json()

    assert (
        client2.get(f"http://localhost:8080/lists/{list_id}").status_code == 404
    )

    client.patch(
        f"http://localhost:8080/lists/{list_id}/collaborators",
        json=[email2]
    ).json()

    assert client2.get(f"http://localhost:8080/lists/{list_id}").json() == {
        **todo_list,
        "collaborators": [email, email2],
    }

    client2.delete(
        f"http://localhost:8080/lists/{list_id}/collaborators", json=[email2]
    )

    assert client2.get(f"http://localhost:8080/lists/{list_id}").status_code == 404
