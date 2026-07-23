import pytest
from api.deps import get_current_admin
from core.services.exceptions import Forbidden
from db.models import User


def test_get_current_admin_returns_user_when_admin():
    user = User(email="a@e.com", is_admin=True)
    assert get_current_admin(user) is user


def test_get_current_admin_raises_forbidden_when_not_admin():
    user = User(email="a@e.com", is_admin=False)
    with pytest.raises(Forbidden):
        get_current_admin(user)
