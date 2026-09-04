"""Unit tests for relationship search-index hooks (no database or Solr)."""
import pytest

import ckanext.relationship.plugin as plugin


@pytest.fixture
def index_document(monkeypatch):
    monkeypatch.setattr(plugin.utils, 'get_relations_info', lambda pkg_type: [])

    def make(related_ids, datasets):
        monkeypatch.setattr(plugin.sch, 'scheming_get_schema',
                            lambda *args: {'dataset_fields': []})

        def get_action(name):
            if name == 'relationship_relations_ids_list':
                return lambda context, data: related_ids
            if name == 'package_show':
                def package_show(context, data):
                    value = datasets[data['id']]
                    if isinstance(value, Exception):
                        raise value
                    return value
                return package_show
            raise AssertionError('unexpected action: %s' % name)

        monkeypatch.setattr(plugin.tk, 'get_action', get_action)
        document = {
            'id': 'molecule-1', 'name': 'molecule-name',
            'title': 'Molecule title', 'type': 'molecule',
            'inchi': 'chemical metadata',
            'vocab_related_dataset': ['existing relationship metadata'],
        }
        return plugin.RelationshipPlugin().before_index(document)
    return make


def test_molecule_with_no_related_datasets_remains_indexable(index_document):
    result = index_document([], {})
    assert result['id'] == 'molecule-1'
    assert result['name'] == 'molecule-name'
    assert result['title'] == 'Molecule title'
    assert result['type'] == 'molecule'
    assert result['inchi'] == 'chemical metadata'
    assert result['vocab_related_dataset'] == ['existing relationship metadata']
    assert 'measurement_technique_proxy' not in result
    assert 'organization_proxy' not in result


@pytest.mark.parametrize('technique', [None, '', '   ', []])
def test_missing_or_empty_technique_is_ignored(index_document, technique):
    result = index_document(['dataset-1'], {
        'dataset-1': {'state': 'active', 'measurement_technique': technique}
    })
    assert 'measurement_technique_proxy' not in result
    assert 'organization_proxy' not in result


def test_string_technique_and_organization_are_trimmed(index_document):
    result = index_document(['dataset-1'], {'dataset-1': {
        'state': 'active', 'measurement_technique': '  Mass spectrometry  ',
        'organization': {'title': '  Repository A  '},
    }})
    assert result['measurement_technique_proxy'] == ['Mass spectrometry']
    assert result['organization_proxy'] == ['Repository A']


def test_list_techniques_are_cleaned_and_deduplicated(index_document):
    result = index_document(['dataset-1'], {'dataset-1': {
        'measurement_technique': [
            'NMR', ' nmr ', None, '', 'Mass spectrometry', 'MASS SPECTROMETRY'
        ]
    }})
    assert result['measurement_technique_proxy'] == ['NMR', 'Mass spectrometry']


def test_multiple_datasets_are_combined_and_deduplicated(index_document):
    result = index_document(['dataset-1', 'dataset-2'], {
        'dataset-1': {'measurement_technique': 'NMR',
                      'organization': {'title': 'Repository A'}},
        'dataset-2': {'measurement_technique': ['nmr', 'IR'],
                      'organization': {'title': ' repository a '}},
    })
    assert result['measurement_technique_proxy'] == ['NMR', 'IR']
    assert result['organization_proxy'] == ['Repository A']


def test_organization_proxy_variants_have_one_canonical_facet(index_document):
    variants = [
        'Chemotion - Repository',
        'Chemotion  -  Repository',
        'Chemotion\t-\tRepository',
        'Chemotion\n-\nRepository',
        ' Chemotion - Repository ',
        'Chemotion - Repository   ',
        'Chemotion\u00a0-\u00a0Repository',
        'Chemotion \u2013 Repository',
        'Chemotion \u2014 Repository',
        'chemotion - repository',
    ]
    result = index_document(
        ['dataset-%d' % index for index in range(len(variants))],
        {'dataset-%d' % index: {'organization': {'title': value}}
         for index, value in enumerate(variants)})

    assert result['organization_proxy'] == ['Chemotion - Repository']
    assert result['organization_proxy'][0].endswith(' ') is False


def test_proxy_normalization_ignores_invalid_and_empty_values():
    target = []
    seen = set()

    plugin._append_unique_strings(
        target, seen, [None, '', '  \u00a0  ', 42, {}, []])

    assert target == []


@pytest.mark.parametrize('dash', ['\u2010', '\u2011', '\u2012', '\u2013',
                                  '\u2014', '\u2212'])
def test_proxy_normalization_converts_supported_unicode_dashes(dash):
    assert plugin._normalize_proxy_value(
        'Chemotion%sRepository' % dash) == 'Chemotion - Repository'


def test_measurement_techniques_normalize_whitespace_but_remain_distinct(
        index_document):
    result = index_document(['dataset-1'], {'dataset-1': {
        'measurement_technique': [
            'Mass\u00a0spectrometry', 'Mass   spectrometry', 'NMR', 'IR'
        ]
    }})

    assert result['measurement_technique_proxy'] == [
        'Mass spectrometry', 'NMR', 'IR'
    ]


def test_unavailable_and_deleted_datasets_do_not_abort(
        index_document, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        plugin.log, 'warning', lambda message, *args: warnings.append(message % args))
    result = index_document(['missing', 'deleted', 'active'], {
        'missing': RuntimeError('not accessible'),
        'deleted': {'state': 'deleted', 'measurement_technique': 'do not index'},
        'active': {'measurement_technique': 'IR'},
    })
    assert result['measurement_technique_proxy'] == ['IR']
    assert any('Failed to fetch related dataset missing' in item for item in warnings)
    assert any('Skipping inactive related dataset deleted' in item for item in warnings)


def test_debug_logging_does_not_require_proxy_fields(index_document, monkeypatch):
    messages = []
    monkeypatch.setattr(
        plugin.log, 'debug', lambda message, *args: messages.append(message % args))
    result = index_document([], {})
    assert 'measurement_technique_proxy' not in result
    assert any('techniques=[] organizations=[]' in item for item in messages)


@pytest.mark.parametrize('technique', [None, 'new technique', 'changed technique'])
def test_dataset_technique_update_rebuilds_each_molecule_once(monkeypatch, technique):
    calls = []
    action_calls = []

    def get_action(name):
        action_calls.append(name)
        if name == 'relationship_relations_ids_list':
            return lambda context, data: ['molecule-1', 'molecule-1']
        if name == 'package_show':
            return lambda context, data: {'type': 'molecule', 'state': 'active'}
        raise AssertionError('relationship mutation was not expected: %s' % name)

    monkeypatch.setattr(plugin.tk, 'get_action', get_action)
    monkeypatch.setattr(plugin, 'rebuild', calls.append)
    plugin.RelationshipPlugin().after_update({}, {
        'id': 'dataset-1', 'type': 'dataset', 'state': 'active',
        'measurement_technique': technique,
    })
    assert calls == ['molecule-1']
    assert 'relationship_relation_create' not in action_calls
    assert 'relationship_relation_delete' not in action_calls


def test_dataset_organization_update_rebuilds_only_active_molecules(monkeypatch):
    calls = []

    def get_action(name):
        if name == 'relationship_relations_ids_list':
            return lambda context, data: ['active', 'deleted', 'not-a-molecule']
        if name == 'package_show':
            packages = {
                'active': {'type': 'molecule', 'state': 'active'},
                'deleted': {'type': 'molecule', 'state': 'deleted'},
                'not-a-molecule': {'type': 'dataset', 'state': 'active'},
            }
            return lambda context, data: packages[data['id']]
        raise AssertionError('unexpected action: %s' % name)

    monkeypatch.setattr(plugin.tk, 'get_action', get_action)
    monkeypatch.setattr(plugin, 'rebuild', calls.append)
    plugin.RelationshipPlugin().after_update({}, {
        'id': 'dataset-1', 'type': 'dataset', 'state': 'active',
        'organization': {'title': 'New repository'},
    })
    assert calls == ['active']


def test_relationship_update_is_preserved_without_double_rebuild(monkeypatch):
    calls = []
    created = []

    def get_action(name):
        if name == 'relationship_relation_create':
            return lambda context, data: created.append(data)
        if name == 'relationship_relations_ids_list':
            return lambda context, data: ['molecule-1']
        if name == 'package_show':
            return lambda context, data: {'type': 'molecule', 'state': 'active'}
        raise AssertionError('unexpected action: %s' % name)

    monkeypatch.setattr(plugin.tk, 'get_action', get_action)
    monkeypatch.setattr(plugin, 'rebuild', calls.append)
    plugin.RelationshipPlugin().after_update({}, {
        'id': 'dataset-1', 'type': 'dataset', 'state': 'active',
        'add_relations': [('molecule-1', 'related_to')],
    })
    assert len(created) == 1
    assert calls.count('molecule-1') == 1
    assert calls.count('dataset-1') == 1


def test_relationship_deletion_is_preserved(monkeypatch):
    calls = []
    deleted = []

    def get_action(name):
        if name == 'relationship_relation_delete':
            return lambda context, data: deleted.append(data)
        if name == 'relationship_relations_ids_list':
            return lambda context, data: []
        raise AssertionError('unexpected action: %s' % name)

    monkeypatch.setattr(plugin.tk, 'get_action', get_action)
    monkeypatch.setattr(plugin, 'rebuild', calls.append)
    plugin.RelationshipPlugin().after_update({}, {
        'id': 'dataset-1', 'type': 'dataset', 'state': 'active',
        'del_relations': [('molecule-1', 'related_to')],
    })

    assert deleted == [{
        'subject_id': 'dataset-1', 'object_id': 'molecule-1',
        'relation_type': 'related_to',
    }]
    assert calls == ['molecule-1', 'dataset-1']


def test_inactive_dataset_update_does_not_rebuild(monkeypatch):
    monkeypatch.setattr(
        plugin.tk, 'get_action',
        lambda name: (_ for _ in ()).throw(AssertionError('unexpected action')))
    calls = []
    monkeypatch.setattr(plugin, 'rebuild', calls.append)
    plugin.RelationshipPlugin().after_update({}, {
        'id': 'dataset-1', 'type': 'dataset', 'state': 'deleted'
    })
    assert calls == []
