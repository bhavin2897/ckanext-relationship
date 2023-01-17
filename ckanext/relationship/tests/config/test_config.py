import pytest

from ckanext.relationship.config import (
    get_max_relationship_number,
    DEF_MAX_RELATIONSHIP_NUM,
    CONF_MAX_RELATIONSHIP_NUM
)


class TestRestrictMaxRelationships:
    def test_default_value(self):
        assert get_max_relationship_number() == DEF_MAX_RELATIONSHIP_NUM

    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "10")
    def test_set(self):
        assert get_max_relationship_number() == 10

    @pytest.mark.ckan_config(CONF_MAX_RELATIONSHIP_NUM, "")
    def test_not_integer(self):
        """If config option is specified, it must be integer"""

        with pytest.raises(ValueError):
            get_max_relationship_number()
