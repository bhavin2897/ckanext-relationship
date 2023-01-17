CONF_MAX_RELATIONSHIP_NUM = "ckanext.relationship.max_relationship_number"
DEF_MAX_RELATIONSHIP_NUM = 5


import ckan.plugins.toolkit as tk


def get_max_relationship_number() -> int:
    """Return a maximum number of relationships for a dataset

    Will be applied only in pair with a schema validator `restrict_max_relationships`

    Returns:
        int: relationships limit (default: 5)
    """
    return tk.asint(tk.config.get(CONF_MAX_RELATIONSHIP_NUM, DEF_MAX_RELATIONSHIP_NUM))
