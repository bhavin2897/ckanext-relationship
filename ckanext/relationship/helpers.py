from __future__ import annotations

import json

import ckan.plugins.toolkit as tk
from ckanext.toolbelt.decorators import Collector

import logging
log = logging.getLogger(__name__)

helper, get_helpers = Collector("relationship").split()


@helper
def get_entity_list(entity, entity_type, include_private=True):
    """Return ids list of specified entity (entity, entity_type)"""
    context = {}
    if entity == 'dataset' or entity == 'molecule':
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
    """ Pull existing relations for form_snippet and display_snippet. """
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


    return current_relation_by_id or current_relation_by_name

@helper
def get_dataset_dict_from_dataset_id(dataset_id):

    try:
        dataset_dict = tk.get_action('package_show')({"ignore_auth": True}, {'id': dataset_id})

    except Exception as e:
        log.warning("Failed to fetch related dataset %s: %s", dataset_id, e)
        pass

    return dataset_dict


@helper
def get_selected_json(selected_ids: list = []) -> str:
    selected_pkgs = []
    for pkg_id in selected_ids:
        try:
            pkg_dict = tk.get_action("package_show")({}, {"id": pkg_id})
            selected_pkgs.append(
                {
                    "name": pkg_dict["id"],
                    "title": pkg_dict["title"],
                    "description": pkg_dict["notes"]
                }
            )
        except:
            continue
    return json.dumps(selected_pkgs)


# Molecule Page Facet

# TODO: This should be updated
@helper
def get_molecule_search_facets(package_type, items, search_facets):
    """
    Dynamically calculate facet values for 'measurement_technique' based on related datasets.
    """
    measurement_technique = []

    item_facet_dict = {
        "name":"",
        "display_name":"",
        "count":""

    }

    # Check for valid items list and related_dataset key
    if not items or 'related_dataset' not in items[0]:
        raise ValueError("Invalid items or missing 'related_dataset'")

    if package_type == 'molecule':
        pkg_id = items[0]['related_dataset'].strip('[]"')
        # pkg_id = '10-14272-rickcznfxytjog-uhfffaoysa-n-chmo0000596-1'
        pkg_dict = tk.get_action("package_show")({}, {"id":f"{pkg_id}"})
        # pkg_dict = tk.get_action("package_search")({}, {"fq": f"id:{pkg_id}","facet": "true"})

        # Extract measurement_technique from pkg_dict if it exists
        measurement_technique =  pkg_dict['measurement_technique']
        # search_facets = pkg_dict.get('search_facets')

        if isinstance(measurement_technique, str):

            item_facet_dict['name'] = measurement_technique
            item_facet_dict['display_name'] = measurement_technique
            item_facet_dict['count'] = 1

    search_facets['measurement_technique']['items'].append(item_facet_dict)
    log.debug(search_facets)

    return search_facets

@helper
def get_dataset_facets_for_molecule_search(molecule_items):
    """
    Fetch search_facets of related datasets to be displayed on the molecule page.
    """
    if not molecule_items:
        log.debug("No molecule items found.")
        return {}

    # Collect related dataset IDs from molecule items

    related_datasets = ()
    for molecule in molecule_items:
        related_datasets = molecule.get("related_dataset", [])
        log.debug(f"related_dataset {related_datasets}")

        if isinstance(related_datasets, str):
            try:
                related_datasets = json.loads(related_datasets)
            except json.JSONDecodeError:
                print("Invalid JSON format for related_datasets")
                related_datasets = []

    related_dataset_ids = []
    related_dataset_ids.extend(dataset_id.strip() for dataset_id in related_datasets)

    if not related_dataset_ids:
        log.debug("No related datasets found for molecules.")
        return {}

    # Query facets for related datasets
    fq_query = " OR ".join([f"id:{dataset_id}" for dataset_id in related_dataset_ids])
    log.debug(f"FQ Query: {fq_query}")
    try:
        dataset_search_results = tk.get_action("package_search")({}, {
            "fq": fq_query,
            "facet": "true",
            #"facet.field": ["measurement_technique", "tags", "organization"]
        })
        return dataset_search_results.get("search_facets", {})
    except Exception as e:
        log.error(f"Failed to fetch dataset facets: {e}")
        pass

