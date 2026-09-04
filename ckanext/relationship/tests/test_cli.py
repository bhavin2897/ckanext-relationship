"""Tests for the controlled proxy-facet maintenance command."""
import json

import pytest
from click.testing import CliRunner

import ckanext.relationship.cli as cli


def _organization_action(name):
    assert name == 'organization_show'
    return lambda context, data: {
        'id': 'organization-id',
        'name': 'chemotion-repository',
        'title': 'Chemotion - Repository ',
    }


def _molecules(*identifiers):
    return [{'id': identifier, 'name': identifier + '-name'}
            for identifier in identifiers]


def test_dry_run_does_not_write_to_solr(monkeypatch):
    monkeypatch.setattr(cli.tk, 'get_action', _organization_action)
    monkeypatch.setattr(cli, '_select_molecules',
                        lambda organization_id: _molecules('molecule-1'))
    monkeypatch.setattr(
        cli, 'rebuild',
        lambda package_id: pytest.fail('dry-run attempted a Solr write'))

    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy',
        '--organization', 'chemotion-repository', '--dry-run'])

    assert result.exit_code == 0
    assert '"status": "validated"' in result.output
    assert 'selected=1 reindexed=0 failed=0 database_changed=false' in result.output


@pytest.mark.parametrize('options, expected_message', [
    ([], 'expected-molecules'),
    (['--expected-molecules', '1'], 'audit-log'),
    (['--expected-molecules', '1', '--audit-log', 'audit.jsonl'], 'confirm'),
])
def test_apply_requires_all_safety_options(options, expected_message):
    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy', '--organization', 'chemotion-repository',
        '--apply'] + options)

    assert result.exit_code == 2
    assert expected_message in result.output


def test_selection_deduplicates_ids_and_uses_only_read_only_sql():
    statements = []

    class Result(object):
        def fetchall(self):
            return [
                ('molecule-2', 'second'),
                ('molecule-1', 'first'),
                ('molecule-1', 'first'),
            ]

    class Session(object):
        def execute(self, statement, parameters):
            statements.append(str(statement))
            assert parameters == {'organization_id': 'organization-id'}
            return Result()

    result = cli._select_molecules('organization-id', session=Session())

    assert result == [
        {'id': 'molecule-1', 'name': 'first'},
        {'id': 'molecule-2', 'name': 'second'},
    ]
    sql = statements[0].upper()
    assert "DATASET.STATE = 'ACTIVE'" in sql
    assert "MOLECULE.STATE = 'ACTIVE'" in sql
    assert "MOLECULE.TYPE = 'MOLECULE'" in sql
    assert 'RELATIONSHIP.SUBJECT_ID IN (DATASET.ID, DATASET.NAME)' in sql
    assert 'RELATIONSHIP.OBJECT_ID IN (DATASET.ID, DATASET.NAME)' in sql
    assert 'RELATED.IDENTIFIER IN (MOLECULE.ID, MOLECULE.NAME)' in sql
    assert not any(keyword in sql for keyword in (
        'INSERT ', 'UPDATE ', 'DELETE ', 'TRUNCATE ', 'ALTER ', 'DROP '))


def test_apply_revalidates_inactive_packages_and_continues_after_failures(
        monkeypatch, tmp_path):
    selected = _molecules('inactive', 'solr-failure', 'success')
    rebuilt = []

    def get_action(name):
        if name == 'organization_show':
            return _organization_action(name)
        if name == 'package_show':
            def package_show(context, data):
                if data['id'] == 'inactive':
                    return {'id': 'inactive', 'name': 'inactive-name',
                            'type': 'molecule', 'state': 'deleted'}
                return {'id': data['id'], 'name': data['id'] + '-name',
                        'type': 'molecule', 'state': 'active'}
            return package_show
        raise AssertionError('unexpected action: %s' % name)

    def rebuild(package_id):
        rebuilt.append(package_id)
        if package_id == 'solr-failure':
            raise RuntimeError('Solr unavailable')

    monkeypatch.setattr(cli.tk, 'get_action', get_action)
    monkeypatch.setattr(cli, '_select_molecules',
                        lambda organization_id: selected)
    monkeypatch.setattr(cli, 'rebuild', rebuild)
    audit_path = str(tmp_path / 'organization-proxy.jsonl')

    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy',
        '--organization', 'chemotion-repository',
        '--apply', '--expected-molecules', '3',
        '--audit-log', audit_path,
        '--confirm', cli.CONFIRMATION,
    ])

    assert result.exit_code == 0
    assert rebuilt == ['solr-failure', 'success']
    with open(audit_path) as audit_file:
        records = [json.loads(line) for line in audit_file]
    assert [record['status'] for record in records] == [
        'failed', 'failed', 'reindexed']
    assert records[0]['error'] == 'Package is no longer an active molecule'
    assert records[1]['error'] == 'Solr unavailable'
    assert all(record['expected_canonical_proxy'] ==
               'Chemotion - Repository' for record in records)
    assert 'selected=3 reindexed=1 failed=2 database_changed=false' in result.output


def test_expected_count_mismatch_performs_no_reindex(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.tk, 'get_action', _organization_action)
    monkeypatch.setattr(cli, '_select_molecules',
                        lambda organization_id: _molecules('molecule-1'))
    monkeypatch.setattr(
        cli, 'rebuild',
        lambda package_id: pytest.fail('count mismatch attempted a Solr write'))

    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy',
        '--organization', 'chemotion-repository',
        '--apply', '--expected-molecules', '2',
        '--audit-log', str(tmp_path / 'audit.jsonl'),
        '--confirm', cli.CONFIRMATION,
    ])

    assert result.exit_code == 1
    assert 'No documents were reindexed' in result.output
