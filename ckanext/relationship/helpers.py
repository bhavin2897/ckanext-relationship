from __future__ import annotations

import ckan.plugins.toolkit as tk
from ckanext.toolbelt.decorators import Collector

helper, get_helpers = Collector("relationship").split()


@helper
def get_entity_list(entity, entity_type, include_private=True):
    """Return ids list of specified entity (entity, entity_type)"""
    context = {}
    if entity == 'package':
        entity_list = tk.get_action('package_search')(context, {'fq': f'type:{entity_type}',
                                                                'fl': 'id, name, title',
                                                                'rows': 1000,
                                                                'include_private': include_private})
        entity_list = entity_list['results']
    else:
        entity_list = tk.get_action('relationship_get_entity_list')(context, {'entity': entity,
                                                                              'entity_type': entity_type})
        entity_list = [{'id': id, 'name': name, 'title': title} for id, name, title in entity_list]
    return entity_list


@helper
def get_current_relations_list(data, field) -> list[str]:
    """Pull existing relations for form_snippet and display_snippet."""
    subject_id = field.get('id')
    subject_name = field.get('name')
    if not subject_id and not subject_name:
        return []
    related_entity = data['related_entity']
    related_entity_type = data['related_entity_type']
    relation_type = data['relation_type']

    current_relation_by_id = []
    current_relation_by_name = []

    if subject_id:
        current_relation_by_id = tk.get_action('relationship_relations_ids_list')({}, {'subject_id': subject_id,
                                                                                       'object_entity': related_entity,
                                                                                       'object_type': related_entity_type,
                                                                                       'relation_type': relation_type})
    if subject_name:
        current_relation_by_name = tk.get_action('relationship_relations_ids_list')({}, {'subject_id': subject_name,
                                                                                         'object_entity': related_entity,
                                                                                         'object_type': related_entity_type,
                                                                                         'relation_type': relation_type})
    return current_relation_by_id + current_relation_by_name
