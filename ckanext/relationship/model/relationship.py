import ckan.logic as logic
import ckan.model as model
from ckan.model.types import make_uuid
from sqlalchemy import Column, Text, or_

from .base import Base


class Relationship(Base):
    __tablename__ = 'relationship_relationship'
    id: str = Column(Text, primary_key=True, default=make_uuid)
    subject_id: str = Column(Text, nullable=False)
    object_id: str = Column(Text, nullable=False)
    relation_type: str = Column(Text, nullable=False)

    reverse_relation_type = {
        'related_to': 'related_to',
        'child_of': 'parent_of',
        'parent_of': 'child_of'
    }

    def __repr__(self):
        return (
            'Relationship('
            f'id={self.id!r},'
            f'subject_id={self.subject_id!r},'
            f'object_id={self.object_id!r},'
            f'relation_type={self.relation_type!r},'
            ')'
        )

    def as_dict(self):
        id = self.id
        subject_id = self.subject_id
        object_id = self.object_id
        relation_type = self.relation_type
        return ({'id': id,
                 'subject_id': subject_id,
                 'object_id': object_id,
                 'relation_type': relation_type
                 })

    @classmethod
    def by_object_id(cls, subject_id, object_id, relation_type):
        subject_name = _entity_name_by_id(subject_id)
        object_name = _entity_name_by_id(object_id)

        return model.Session.query(cls). \
            filter(or_(cls.subject_id == subject_id,
                       cls.subject_id == subject_name)). \
            filter(or_(cls.object_id == object_id,
                       cls.object_id == object_name)). \
            filter(cls.relation_type == relation_type).one_or_none()

    @classmethod
    def by_subject_id(cls, subject_id, object_entity, object_type=None, relation_type=None):
        subject_name = _entity_name_by_id(subject_id)

        q = model.Session.query(cls).filter(or_(cls.subject_id == subject_id,
                                                cls.subject_id == subject_name))

        if object_entity:
            object_class = logic.model_name_to_class(model, object_entity)
            q = q.filter(or_(object_class.id == cls.object_id,
                             object_class.name == cls.object_id))

            if object_type:
                q = q.filter(object_class.type == object_type)

        if relation_type:
            q = q.filter(cls.relation_type == relation_type)

        return q.distinct().all()


def _entity_name_by_id(entity_id):
    """
    Returns entity (package or organization or group) name by its id
    """

    pkg = model.Session.query(model.Package).filter(model.Package.id == entity_id).one_or_none()
    if pkg:
        return pkg.name
    group = model.Session.query(model.Group).filter(model.Group.id == entity_id).one_or_none()
    if pkg:
        return group.name
