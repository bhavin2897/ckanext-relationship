"""Tests for the controlled proxy-facet maintenance command."""
import json
import re

import pytest
from click.testing import CliRunner

import ckanext.relationship.cli as cli


def _organization():
    return {
        'id': 'organization-id',
        'name': 'chemotion-repository',
        'title': 'Chemotion - Repository ',
        'type': 'repository',
        'state': 'active',
        'is_organization': True,
    }


def _molecules(*identifiers):
    return [{'id': identifier, 'name': identifier + '-name'}
            for identifier in identifiers]


def test_dry_run_does_not_write_to_solr(monkeypatch):
    monkeypatch.setattr(
        cli, '_load_active_organization',
        lambda session, reference: _organization())
    monkeypatch.setattr(
        cli.tk, 'get_action',
        lambda name: pytest.fail('%s action was called' % name))
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
    assert '"organization_type": "repository"' in result.output
    assert 'selected=1 reindexed=0 failed=0 database_changed=false' in result.output


@pytest.mark.parametrize('reference, organization_type', [
    ('chemotion-repository', 'repository'),
    ('11111111-2222-3333-4444-555555555555', 'organization'),
])
def test_organization_lookup_works_by_name_or_uuid(
        reference, organization_type):
    statements = []

    class Result(object):
        def fetchone(self):
            return ('organization-id', 'chemotion-repository',
                    'Chemotion - Repository', organization_type, 'active', True)

    class Session(object):
        def execute(self, statement, parameters):
            statements.append(str(statement))
            assert parameters == {'organization': reference}
            return Result()

    assert cli._load_active_organization(Session(), reference) == {
        'id': 'organization-id',
        'name': 'chemotion-repository',
        'title': 'Chemotion - Repository',
        'type': organization_type,
        'state': 'active',
        'is_organization': True,
    }
    sql = statements[0].upper()
    assert sql.lstrip().startswith('SELECT ')
    assert 'FROM PUBLIC."GROUP"' in sql
    assert re.search(r"ID\s*=\s*:ORGANIZATION", sql)
    assert re.search(r"NAME\s*=\s*:ORGANIZATION", sql)
    assert re.search(r"IS_ORGANIZATION\s+IS\s+TRUE", sql)
    assert re.search(r"\b(?:INSERT|UPDATE|DELETE)\b", sql) is None


@pytest.mark.parametrize('row, expected_message', [
    (None, 'was not found'),
    (('organization-id', 'deleted', 'Deleted', 'repository', 'deleted', True),
     'is not active'),
    (('group-id', 'ordinary-group', 'Ordinary group', 'group', 'active', False),
     'is not an organization'),
])
def test_invalid_organization_is_rejected(row, expected_message):
    class Result(object):
        def fetchone(self):
            return row

    class Session(object):
        def execute(self, statement, parameters):
            return Result()

    with pytest.raises(cli.MoleculeProxyReindexError) as error:
        cli._load_active_organization(Session(), 'organization-reference')
    assert expected_message in str(error.value)


def test_dry_run_uses_only_selects_without_request_context(monkeypatch):
    statements = []

    class Result(object):
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

        def fetchall(self):
            return self.rows

    class Session(object):
        def execute(self, statement, parameters):
            sql = str(statement)
            statements.append(sql)
            if 'public."group"' in sql:
                return Result([(
                    'organization-id', 'chemotion-repository',
                    'Chemotion - Repository', 'repository', 'active', True)])
            return Result([('molecule-1', 'molecule-name')])

    monkeypatch.setattr(cli.model, 'Session', Session())
    monkeypatch.setattr(
        cli.tk, 'get_action',
        lambda name: pytest.fail('%s action was called' % name))
    monkeypatch.setattr(
        cli, 'rebuild',
        lambda package_id: pytest.fail('dry-run attempted a Solr write'))

    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy',
        '--organization', 'chemotion-repository', '--dry-run'])

    assert result.exit_code == 0
    assert len(statements) == 2
    assert all(statement.lstrip().upper().startswith(
        ('SELECT ', 'WITH ')) for statement in statements)
    assert all(re.search(r"\b(?:INSERT|UPDATE|DELETE)\b",
                         statement.upper()) is None
               for statement in statements)


def test_unexpected_selection_error_is_concise(monkeypatch):
    def fail(session, reference):
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(cli, '_load_active_organization', fail)
    result = CliRunner().invoke(cli.relationship, [
        'reindex-organization-proxy',
        '--organization', 'chemotion-repository', '--dry-run'])

    assert result.exit_code == 1
    assert 'Error: Unable to select molecules' in result.output
    assert 'database unavailable' in result.output
    assert 'Traceback' not in result.output


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
    dataset_sql = sql.split('), RELATED_IDENTIFIERS', 1)[0]
    assert re.search(r"(?:DATASET\.)?TYPE\s*=\s*'DATASET'", dataset_sql)
    assert re.search(r"(?:DATASET\.)?STATE\s*=\s*'ACTIVE'", dataset_sql)
    assert re.search(
        r"OWNER_ORG\s*=\s*:ORGANIZATION_ID", dataset_sql)
    assert re.search(r"MOLECULE\.STATE\s*=\s*'ACTIVE'", sql)
    assert re.search(r"MOLECULE\.TYPE\s*=\s*'MOLECULE'", sql)
    assert len(re.findall(
        r"RELATIONSHIP\.RELATION_TYPE\s*=\s*'RELATED_TO'", sql)) == 2
    assert 'RELATIONSHIP.SUBJECT_ID IN (DATASET.ID, DATASET.NAME)' in sql
    assert 'RELATIONSHIP.OBJECT_ID IN (DATASET.ID, DATASET.NAME)' in sql
    assert 'RELATED.IDENTIFIER IN (MOLECULE.ID, MOLECULE.NAME)' in sql
    assert re.search(r"\b(?:INSERT|UPDATE|DELETE)\b", sql) is None
    assert re.search(r"\b(?:TRUNCATE|ALTER|DROP)\b", sql) is None


def test_apply_revalidates_inactive_packages_and_continues_after_failures(
        monkeypatch, tmp_path):
    selected = _molecules('inactive', 'solr-failure', 'success')
    rebuilt = []

    def get_action(name):
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
    monkeypatch.setattr(
        cli, '_load_active_organization',
        lambda session, reference: _organization())
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
    assert all(record['organization_type'] == 'repository'
               for record in records)
    assert all(record['expected_canonical_proxy'] ==
               'Chemotion - Repository' for record in records)
    assert 'selected=3 reindexed=1 failed=2 database_changed=false' in result.output


def test_expected_count_mismatch_performs_no_reindex(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli, '_load_active_organization',
        lambda session, reference: _organization())
    monkeypatch.setattr(
        cli.tk, 'get_action',
        lambda name: pytest.fail('%s action was called' % name))
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
