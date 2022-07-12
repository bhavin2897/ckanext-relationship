import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckanext.relationship.helpers as helpers
import ckanext.relationship.logic.action as action
import ckanext.relationship.logic.auth as auth
import ckanext.relationship.logic.validators as validators
import ckanext.relationship.utils as utils
import ckanext.scheming.helpers as sch
from ckan.lib.search import rebuild
from ckan.logic import NotFound


class RelationshipPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IPackageController, inherit=True)

    # IConfigurer
    def update_config(self, config_):
        tk.add_template_directory(config_, 'templates')
        tk.add_public_directory(config_, 'public')
        tk.add_resource('fanstatic', 'relationship')

    # IActions
    def get_actions(self):
        return action.get_actions()

    # IAuthFunctions
    def get_auth_functions(self):
        return auth.get_auth_functions()

    # IValidators
    def get_validators(self):
        return validators.get_validators()

    # ITemplateHelpers
    def get_helpers(self):
        return helpers.get_helpers()

    # IPackageController
    def after_create(self, context, pkg_dict):
        context = context.copy()
        context.pop("__auth_audit", None)
        return _update_relations(context, pkg_dict)

    def after_update(self, context, pkg_dict):
        context = context.copy()
        context.pop("__auth_audit", None)
        return _update_relations(context, pkg_dict)

    def before_index(self, pkg_dict):
        pkg_id = pkg_dict['id']
        pkg_type = pkg_dict['type']
        schema = sch.scheming_get_schema('dataset', pkg_type)
        if not schema:
            return pkg_dict
        relations_info = utils.get_relations_info(pkg_type)
        for related_entity, related_entity_type, relation_type in relations_info:
            relations_ids = tk.get_action('relationship_relations_ids_list')({}, {'subject_id': pkg_id,
                                                                                  'object_entity': related_entity,
                                                                                  'object_type': related_entity_type,
                                                                                  'relation_type': relation_type})

            if not relations_ids:
                continue
            field = utils.get_relation_field(pkg_type, related_entity, related_entity_type, relation_type)
            pkg_dict[f'vocab_{field["field_name"]}'] = relations_ids

            del pkg_dict[field["field_name"]]

        return pkg_dict

    def after_show(self, context, pkg_dict):
        pkg_id = pkg_dict['id']
        pkg_type = pkg_dict['type']
        relations_info = utils.get_relations_info(pkg_type)
        for related_entity, related_entity_type, relation_type in relations_info:
            field = utils.get_relation_field(pkg_type, related_entity, related_entity_type, relation_type)
            pkg_dict[field['field_name']] = \
                tk.get_action('relationship_relations_ids_list')(context, {'subject_id': pkg_id,
                                                                           'object_entity': related_entity,
                                                                           'object_type': related_entity_type,
                                                                           'relation_type': relation_type})


def _update_relations(context, pkg_dict):
    subject_id = pkg_dict['id']
    add_relations = pkg_dict.get('add_relations', [])
    del_relations = pkg_dict.get('del_relations', [])
    for object_id, relation_type in add_relations + del_relations:
        if (object_id, relation_type) in add_relations:
            tk.get_action('relationship_relation_create')(context, {'subject_id': subject_id,
                                                                    'object_id': object_id,
                                                                    'relation_type': relation_type})
        else:
            tk.get_action('relationship_relation_delete')(context, {'subject_id': subject_id,
                                                                    'object_id': object_id,
                                                                    'relation_type': relation_type})

        try:
            tk.get_action('package_show')(context, {'id': object_id})
            rebuild(object_id)
        except NotFound:
            pass
    rebuild(subject_id)
    return pkg_dict
