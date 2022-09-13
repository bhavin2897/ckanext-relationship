from __future__ import annotations

import ckan.logic as logic
import ckan.plugins.toolkit as tk
import ckanext.relationship.logic.schema as schema
from ckan.logic import validate
from ckanext.relationship.model.relationship import Relationship
from ckanext.relationship.utils import pkg_name_by_id
from ckanext.toolbelt.decorators import Collector
from sqlalchemy import or_

NotFound = logic.NotFound

action, get_actions = Collector("relationship").split()


@action
@validate(schema.relation_create)
def relation_create(context, data_dict) -> list[dict[str, str]]:
    """Create relation with specified type (relation_type) between two entities specified
    by ids (subject_id, object_id). Also create reverse relation."""
    tk.check_access('relationship_relation_create', context, data_dict)

    subject_id = data_dict['subject_id']
    object_id = data_dict['object_id']
    relation_type = data_dict.get('relation_type')

    if Relationship.by_object_id(subject_id, object_id, relation_type):
        return

    relation = Relationship(
        subject_id=subject_id,
        object_id=object_id,
        relation_type=relation_type
    )

    reverse_relation = Relationship(
        subject_id=object_id,
        object_id=subject_id,
        relation_type=Relationship.reverse_relation_type[relation_type]
    )

    context['session'].add(relation)
    context['session'].add(reverse_relation)
    context['session'].commit()

    return [rel.as_dict() for rel in (relation, reverse_relation)]


@action
@validate(schema.relation_delete)
def relation_delete(context, data_dict) -> list[dict[str, str]]:
    """Delete relation with specified type (relation_type) between two entities specified
    by ids (subject_id, object_id). Also delete reverse relation."""
    tk.check_access('relationship_relation_delete', context, data_dict)

    subject_id = data_dict['subject_id']
    subject_name = pkg_name_by_id(data_dict['subject_id'])
    object_id = data_dict['object_id']
    object_name = pkg_name_by_id(data_dict['object_id'])
    relation_type = data_dict.get('relation_type')

    relation = (
        context['session'].query(Relationship)
        .filter(or_(Relationship.subject_id == subject_id,
                    Relationship.subject_id == subject_name),
                or_(Relationship.object_id == object_id,
                    Relationship.object_id == object_name),
                Relationship.relation_type == relation_type)
        .all()
    )

    reverse_relation = (
        context['session'].query(Relationship)
        .filter(or_(Relationship.subject_id == object_id,
                    Relationship.subject_id == object_name),
                or_(Relationship.object_id == subject_id,
                    Relationship.object_id == subject_name),
                Relationship.relation_type == Relationship.reverse_relation_type[
                    relation_type])
        .all()
    )

    [context['session'].delete(rel) for rel in relation]
    [context['session'].delete(rel) for rel in reverse_relation]
    context['session'].commit()
    return [rel[0].as_dict() for rel in (relation, reverse_relation) if len(rel) > 0]


@action
@validate(schema.relations_list)
def relations_list(context, data_dict) -> list[dict[str, str]]:
    """Return dicts list of relation of specified entity (object_entity, object_type) related with specified
    type of relation (relation_type) with entity specified by id (subject_id)."""
    tk.check_access('relationship_relations_list', context, data_dict)

    subject_id = data_dict['subject_id']
    object_entity = data_dict['object_entity']
    object_entity = object_entity if object_entity != 'organization' else 'group'
    object_type = data_dict['object_type']
    relation_type = data_dict.get('relation_type')

    relations = Relationship.by_object_type(subject_id,
                                            object_entity,
                                            object_type,
                                            relation_type)
    if not relations:
        return []
    return [rel.as_dict() for rel in relations]


@action
@validate(schema.relations_ids_list)
def relations_ids_list(context, data_dict) -> list[str]:
    """Return ids list of specified entity (object_entity, object_type) related with specified
    type of relation (relation_type) with entity specified by id (subject_id)."""
    tk.check_access('relationship_relations_ids_list', context, data_dict)

    rel_list = relations_list(context, data_dict)

    return list(set([rel["object_id"] for rel in rel_list]))


@action
@validate(schema.get_entity_list)
def get_entity_list(context, data_dict) -> list[str]:
    """Return ids list of specified entity (entity, entity_type)"""
    tk.check_access('relationship_get_entity_list', context, data_dict)

    model = context['model']

    entity = data_dict['entity']
    entity = entity if entity != 'organization' else 'group'

    entity_type = data_dict['entity_type']

    entity_class = logic.model_name_to_class(model, entity)

    entity_list = (context['session'].query(entity_class.id, entity_class.name, entity_class.title)
                   .filter(entity_class.state != 'deleted')
                   .filter(entity_class.type == entity_type).all())

    return entity_list
