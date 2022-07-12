from __future__ import annotations

from ckan.plugins import toolkit as tk
from ckanext.toolbelt.decorators import Collector

auth, get_auth_functions = Collector("relationship").split()


@auth
def relation_create(context, data_dict):
    return {'success': True}


@auth
def relation_delete(context, data_dict):
    return {'success': True}


@auth
@tk.auth_allow_anonymous_access
def relations_list(context, data_dict):
    return {'success': True}


@auth
@tk.auth_allow_anonymous_access
def relations_ids_list(context, data_dict):
    return {'success': True}


@auth
@tk.auth_allow_anonymous_access
def get_entity_list(context, data_dict):
    return {'success': True}
