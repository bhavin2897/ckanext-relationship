import pytest
from pytest_factoryboy import register
from faker import Faker

from ckan.tests import factories


fake = Faker()


@register
class ResourceFactory(factories.Resource):
    pass


@register
class UserFactory(factories.User):
    pass


@register
class DatasetFactory(factories.Dataset):
    pass


@register
class SysadminFactory(factories.Sysadmin):
    pass


@pytest.fixture
def clean_db(reset_db, migrate_db_for):
    reset_db()

    migrate_db_for("relationship")
