import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckanext.relationship.helpers as helpers
import ckanext.relationship.cli as cli
import ckanext.relationship.views as views
import ckanext.relationship.logic.action as action
import ckanext.relationship.logic.auth as auth
import ckanext.relationship.logic.validators as validators
import ckanext.relationship.utils as utils
import ckanext.scheming.helpers as sch
from ckan.lib.search import rebuild
from ckan.logic import NotFound
from collections import Counter
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

DASHES = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2212]")
WHITESPACE = re.compile(r"\s+")
WHITESPACE_AROUND_DASH = re.compile(r"\s*-\s*")


class RelationshipPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IPackageController, inherit=True)

    # IConfigurer
    def update_config(self, config_):
        tk.add_template_directory(config_, 'templates')
        tk.add_public_directory(config_, 'public')
        tk.add_resource('assets', 'relationship')

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

    # IBlueprint
    def get_blueprint(self):
        return views.get_blueprints()

    # IClick
    def get_commands(self):
        return cli.get_commands()

    # IPackageController
    def after_create(self, context, pkg_dict):
        context = context.copy()
        context.pop("__auth_audit", None)
        return _update_relations(context, pkg_dict)

    def after_update(self, context, pkg_dict):
        context = context.copy()
        context.pop("__auth_audit", None)
        rebuilt_ids = set()
        result = _update_relations(context, pkg_dict, rebuilt_ids)

        if pkg_dict.get('type') == 'dataset' and pkg_dict.get('state', 'active') == 'active':
            _rebuild_related_molecules(context, pkg_dict['id'], rebuilt_ids)

        return result

    def after_delete(self, context, pkg_dict):
        context = context.copy()
        context.pop("__auth_audit", None)

        subject_id = pkg_dict["id"]

        relations_ids_list = tk.get_action('relationship_relations_ids_list')(context, {'subject_id': subject_id})

        for object_id in relations_ids_list:
            tk.get_action('relationship_relation_delete')(context, {'subject_id': subject_id, 'object_id': object_id})

            try:
                rebuild(object_id)
            except NotFound:
                pass
        rebuild(subject_id)

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

            pkg_dict.pop(field["field_name"], None)

        if pkg_type == 'molecule':
            _enrich_molecule_document(pkg_dict)

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


def _update_relations(context, pkg_dict, rebuilt_ids=None):
    if rebuilt_ids is None:
        rebuilt_ids = set()
    subject_id = pkg_dict['id']
    add_relations = pkg_dict.get('add_relations', [])
    del_relations = pkg_dict.get('del_relations', [])
    if not add_relations and not del_relations:
        return pkg_dict
    for object_id, relation_type in del_relations + add_relations:
        if (object_id, relation_type) in add_relations:
            tk.get_action('relationship_relation_create')(context, {'subject_id': subject_id,
                                                                    'object_id': object_id,
                                                                    'relation_type': relation_type})
        else:
            tk.get_action('relationship_relation_delete')(context, {'subject_id': subject_id,
                                                                    'object_id': object_id,
                                                                    'relation_type': relation_type})

        try:
            rebuild(object_id)
            rebuilt_ids.add(object_id)
        except NotFound:
            pass
    rebuild(subject_id)
    rebuilt_ids.add(subject_id)
    return pkg_dict


def _normalize_proxy_value(value):
    """Return a canonical display value for a proxy facet label."""
    if not isinstance(value, str):
        return None

    value = unicodedata.normalize("NFKC", value)
    value = DASHES.sub("-", value)
    value = WHITESPACE.sub(" ", value).strip()
    value = WHITESPACE_AROUND_DASH.sub(" - ", value)
    value = WHITESPACE.sub(" ", value).strip()
    return value or None


def _append_unique_strings(target, seen, values):
    """Append non-empty strings once, comparing values case-insensitively."""
    if isinstance(values, str):
        values = [values]
    elif not isinstance(values, (list, tuple)):
        return

    for value in values:
        value = _normalize_proxy_value(value)
        if value is None:
            continue
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            target.append(value)


def _enrich_molecule_document(pkg_dict):
    pkg_id = pkg_dict.get('id')
    techniques = []
    organizations = []
    technique_keys = set()
    organization_keys = set()

    try:
        related_dataset_ids = tk.get_action('relationship_relations_ids_list')(
            {}, {
                'subject_id': pkg_id,
                'object_entity': 'package',
                'object_type': 'dataset',
                'relation_type': 'related_to'
            }) or []
    except Exception as error:
        log.warning("Failed to resolve related datasets for molecule %s: %s", pkg_id, error)
        related_dataset_ids = []

    for related_dataset_id in related_dataset_ids:
        try:
            related_dataset = tk.get_action('package_show')(
                {'ignore_auth': True}, {'id': related_dataset_id})
            if related_dataset.get('state', 'active') != 'active':
                log.warning(
                    "Skipping inactive related dataset %s while indexing molecule %s",
                    related_dataset_id, pkg_id)
                continue

            _append_unique_strings(
                techniques, technique_keys,
                related_dataset.get('measurement_technique'))

            organization = related_dataset.get('organization') or {}
            if isinstance(organization, dict):
                _append_unique_strings(
                    organizations, organization_keys, organization.get('title'))
        except Exception as error:
            log.warning(
                "Failed to fetch related dataset %s while indexing molecule %s: %s",
                related_dataset_id, pkg_id, error)

    if techniques:
        pkg_dict['measurement_technique_proxy'] = techniques
    else:
        pkg_dict.pop('measurement_technique_proxy', None)

    if organizations:
        pkg_dict['organization_proxy'] = organizations
    else:
        pkg_dict.pop('organization_proxy', None)

    log.debug(
        "Molecule indexing package=%s techniques=%s organizations=%s",
        pkg_id, techniques, organizations)


def _rebuild_related_molecules(context, dataset_id, rebuilt_ids):
    try:
        molecule_ids = tk.get_action('relationship_relations_ids_list')(
            context, {
                'subject_id': dataset_id,
                'object_entity': 'package',
                'object_type': 'molecule',
                'relation_type': 'related_to'
            }) or []
    except Exception:
        log.exception("Failed to find molecules related to dataset %s", dataset_id)
        raise

    for molecule_id in set(molecule_ids):
        if molecule_id in rebuilt_ids:
            continue
        try:
            molecule = tk.get_action('package_show')(
                dict(context, ignore_auth=True), {'id': molecule_id})
        except Exception as error:
            log.warning(
                "Skipping unavailable molecule %s related to dataset %s: %s",
                molecule_id, dataset_id, error)
            continue

        if (molecule.get('type') != 'molecule' or
                molecule.get('state', 'active') != 'active'):
            continue

        try:
            rebuild(molecule_id)
            rebuilt_ids.add(molecule_id)
        except Exception:
            log.exception(
                "Failed to rebuild molecule %s after dataset %s update",
                molecule_id, dataset_id)
            raise
