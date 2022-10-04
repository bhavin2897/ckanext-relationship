from __future__ import annotations

import ckan.plugins.toolkit as tk
import ckanext.scheming.helpers as sch
from ckan.logic import NotFound


def get_relations_info(pkg_type: str) -> list[tuple[str, str, str]]:
    """Return information about relation (related_entity, related_entity_type, relation_type)
    of specified package type (pkg_type) from schema.

    Returns:
        List of tuples of related entities: entity, entity_type, relation_type.
    """
    schema = sch.scheming_get_schema('dataset', pkg_type)
    if not schema:
        return []
    return [(field['related_entity'], field['related_entity_type'], field['relation_type'])
            for field in schema['dataset_fields'] if 'relationship_related_entity' in field.get('validators', '')]


def get_relation_field(pkg_type: str, object_entity: str, object_entity_type: str, relation_type: str) \
        -> dict[str, str]:
    """Return field dict for specified package type (pkg_type) describes relation with specified entity
    (object_entity, object_entity_type) and type of relation (relation_type)."""
    schema = sch.scheming_get_schema('dataset', pkg_type)
    if not schema:
        return []
    for field in schema['dataset_fields']:
        if (
                field.get('related_entity') == object_entity and
                field.get('related_entity_type') == object_entity_type and
                field.get('relation_type') == relation_type
        ):
            return field
    return {}


def entity_name_by_id(entity_id):
    """
    Returns pkg name by its id
    """

    try:
        pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": entity_id})
        if pkg:
            return pkg.get("name")
    except NotFound:
        pass

    try:
        org = tk.get_action("organization_show")({"ignore_auth": True}, {"id": entity_id})
        if org:
            return org.get("name")
    except NotFound:
        pass

    try:
        group = tk.get_action("group_show")({"ignore_auth": True}, {"id": entity_id})
        if group:
            return group.get("name")
    except NotFound:
        pass

