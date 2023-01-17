import pytest

import ckan.lib.navl.dictization_functions as df

from ckanext.relationship.logic.validators import restrict_max_relationships
from ckanext.relationship.config import (
    CONF_MAX_RELATIONSHIP_NUM,
)


@pytest.fixture
def test_data():
    class test_data:
        pass

    test_data = test_data()

    test_data.key = ("field",)
    test_data.errors = {test_data.key: []}
    test_data.err_msg = "The number of relationships for a dataset is limited to 5"

    return test_data


def _call_validator(test_data, data):
    restrict_max_relationships(test_data.key, data, test_data.errors, {})


class TestRestrictMaxRelationships:
    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "5")
    def test_exceed_limit(self, test_data):
        """Throws exception if number of relationships is exceed the limit"""
        with pytest.raises(df.StopOnError):
            _call_validator(test_data, {test_data.key: [f"ds-{n}" for n in range(10)]})

        assert test_data.err_msg in test_data.errors[test_data.key]

    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "10")
    def test_behing_limit(self, test_data):
        """No exception if number of relationships is behind the limit"""
        _call_validator(test_data, {test_data.key: [f"id" for _ in range(5)]})

    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "5")
    def test_equals_limit(self, test_data):
        """No exception if number of relationships is equals to the limit"""
        _call_validator(test_data, {test_data.key: [f"id" for _ in range(5)]})

    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "0")
    def test_zero_means_no_limit(self, test_data):
        """We treat zero as no limit, because otherwise it will prevent user to
        use the field at all"""
        _call_validator(test_data, {test_data.key: [f"id" for _ in range(5)]})
