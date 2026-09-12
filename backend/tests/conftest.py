import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(email="researcher@example.com", name="Ada Researcher", password="StrongPassphrase42!")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="other@example.com", name="Other User", password="StrongPassphrase42!")


@pytest.fixture
def client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client

