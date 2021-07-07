import json

import ckan.plugins.toolkit as tk
import six
from ckanext.scheming.validation import scheming_validator, scheming_multiple_choice_output
from ckantoolkit import missing

_validators = {}


def validator(func):
    func.__name__ = f'relationship_{func.__name__}'
    _validators[func.__name__] = func


def get_validators():
    return _validators.copy()


@validator
@scheming_validator
def related_entity(field, schema):
    related_entity = field.get('related_entity')
    related_entity_type = field.get('related_entity_type')
    relation_type = field.get('relation_type')

    def validator(key, data, errors, context):
        if field.get('required') and data[key] is missing:
            errors[key].append(tk._('Select at least one'))

        entity_id = data.get(('id',))
        entity_name = data.get(('name',))

        if errors[key] or not entity_name:
            return
        if not entity_id or entity_id == entity_name:
            entities = tk.get_action('relationship_get_entity_list')(context, {'entity': field['current_entity'],
                                                                               'entity_type': field[
                                                                                   'current_entity_type']})
            for entity in entities:
                if entity[1] == entity_name:
                    entity_id = entity[0]
        current_relation_by_name = tk.get_action('relationship_relations_list')({}, {'subject_id': entity_name,
                                                                                     'object_entity': related_entity,
                                                                                     'object_type': related_entity_type,
                                                                                     'relation_type': relation_type})
        current_relation_by_name = [rel['object_id'] for rel in current_relation_by_name]
        current_relation_by_name = set(current_relation_by_name)

        if current_relation_by_name:
            for related_entity_id in current_relation_by_name:
                tk.get_action('relationship_relation_create')({}, {'subject_id': entity_id,
                                                                   'object_id': related_entity_id,
                                                                   'relation_type': relation_type
                                                                   })
                tk.get_action('relationship_relation_delete')({}, {'subject_id': entity_name,
                                                                   'object_id': related_entity_id,
                                                                   'relation_type': relation_type
                                                                   })

        if entity_id:
            current_relation = tk.get_action('relationship_relations_list')({}, {'subject_id': entity_id,
                                                                                 'object_entity': related_entity,
                                                                                 'object_type': related_entity_type,
                                                                                 'relation_type': relation_type})
            current_relation = [rel['object_id'] for rel in current_relation]
        else:
            current_relation = []
        current_relation = set(current_relation)

        selected_relation = data[key]
        if selected_relation is not missing:
            selected_relation = scheming_multiple_choice_output(data[key])
            selected_relation = [] if selected_relation == [''] else selected_relation
        else:
            selected_relation = []
        selected_relation = set(selected_relation)

        add_relation = selected_relation - current_relation
        del_relation = current_relation - selected_relation

        current_entity_id = entity_id or entity_name

        for related_entity_id in add_relation | del_relation:
            if related_entity_id in add_relation:
                tk.get_action('relationship_relation_create')({}, {'subject_id': current_entity_id,
                                                                   'object_id': related_entity_id,
                                                                   'relation_type': relation_type
                                                                   })
            else:
                tk.get_action('relationship_relation_delete')({}, {'subject_id': current_entity_id,
                                                                   'object_id': related_entity_id,
                                                                   'relation_type': relation_type
                                                                   })

        data[key] = json.dumps([value for value in selected_relation])

    return validator
