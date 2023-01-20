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
def remove_all_projects(client):
    yield
    projects = client.get("http://localhost:8080/projects").json()
    for project in projects:
        client.delete(f"http://localhost:8080/projects/{project['project_id']}")


def test_project_create(client, email):
    # warm-up the cache
    client.get(f"http://localhost:8080/projects")

    name = token_urlsafe(8)
    create_project = client.post(
        "http://localhost:8080/projects", json=dict(name=name)
    ).json()

    assert create_project["project_id"]
    assert create_project["name"] == name

    project = client.get(
        f"http://localhost:8080/projects/{create_project['project_id']}"
    ).json()

    assert project["project_id"] == create_project["project_id"]
    assert project["name"] == name
    assert project["collaborators"] == [dict(email=email, role="owner")]
    assert project["areas"] == []

    projects = client.get("http://localhost:8080/projects").json()
    assert projects == [dict(project_id=create_project["project_id"], name=name)]


@pytest.fixture
def project_id(client):
    name = token_urlsafe(8)
    create_project = client.post(
        "http://localhost:8080/projects", json=dict(name=name)
    ).json()
    return create_project["project_id"]


def test_area_create(client, project_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/projects/{project_id}")
    client.get(f"http://localhost:8080/projects/{project_id}/areas")

    name = token_urlsafe(8)
    create_area = client.post(
        f"http://localhost:8080/projects/{project_id}/areas", json=dict(name=name)
    ).json()

    assert create_area["area_id"]
    assert create_area["name"] == name

    area = client.get(
        f"http://localhost:8080/projects/{project_id}/areas/{create_area['area_id']}"
    ).json()
    assert area["area_id"] == create_area["area_id"]
    assert area["name"] == name

    areas = client.get(f"http://localhost:8080/projects/{project_id}/areas").json()
    assert areas == [
        dict(
            area_id=create_area["area_id"], name=name, scenario=create_area["scenario"]
        )
    ]

    project = client.get(f"http://localhost:8080/projects/{project_id}").json()
    assert project["areas"] == [
        dict(
            area_id=create_area["area_id"], name=name, scenario=create_area["scenario"]
        )
    ]


@pytest.fixture
def area_id(project_id, client):
    name = token_urlsafe(8)
    create_area = client.post(
        f"http://localhost:8080/projects/{project_id}/areas", json=dict(name=name)
    ).json()
    return create_area["area_id"]


def test_area_delete(client, project_id, area_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/projects/{project_id}")
    client.get(f"http://localhost:8080/projects/{project_id}/areas")
    client.get(f"http://localhost:8080/projects/{project_id}/areas/{area_id}")

    client.delete(f"http://localhost:8080/projects/{project_id}/areas/{area_id}")

    area_status = client.get(
        f"http://localhost:8080/projects/{project_id}/areas/{area_id}"
    ).status_code
    assert area_status == 404

    areas = client.get(f"http://localhost:8080/projects/{project_id}/areas").json()
    assert areas == []

    project = client.get(f"http://localhost:8080/projects/{project_id}").json()
    assert project["areas"] == []


def test_project_delete(client, project_id, area_id):
    # warm-up the cache
    client.get(f"http://localhost:8080/projects/{project_id}")
    client.get(f"http://localhost:8080/projects/{project_id}/areas")
    client.get(f"http://localhost:8080/projects/{project_id}/areas/{area_id}")
    client.get(f"http://localhost:8080/projects/{project_id}/areas/{area_id}/nodes")

    client.delete(f"http://localhost:8080/projects/{project_id}")

    area_status = client.get(
        f"http://localhost:8080/projects/{project_id}/areas/{area_id}"
    ).status_code
    assert area_status == 404

    areas_status = client.get(
        f"http://localhost:8080/projects/{project_id}/areas"
    ).status_code
    assert areas_status == 404

    project_status = client.get(
        f"http://localhost:8080/projects/{project_id}"
    ).status_code
    assert project_status == 404

    projects = client.get(f"http://localhost:8080/projects").json()
    assert projects == []


def test_collaborators(project_id, client, email, client2, email2):
    project = client.get(f"http://localhost:8080/projects/{project_id}").json()

    assert (
        client2.get(f"http://localhost:8080/projects/{project_id}").status_code == 404
    )

    collaborators = client.patch(
        f"http://localhost:8080/projects/{project_id}/collaborators",
        json=[dict(email=email2, role="manager")],
    ).json()

    assert client2.get(f"http://localhost:8080/projects/{project_id}").json() == {
        **project,
        "collaborators": collaborators,
    }

    client2.delete(
        f"http://localhost:8080/projects/{project_id}/collaborators", json=[email]
    )

    assert client.get(f"http://localhost:8080/projects/{project_id}").status_code == 404
