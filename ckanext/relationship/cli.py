"""Controlled maintenance commands for relationship-derived search fields."""
import datetime
import functools
import json

import click
import ckan.model as model
import ckan.plugins.toolkit as tk
from ckan.lib.search import rebuild
from sqlalchemy import text

CONFIRMATION = 'REINDEX_NORMALIZED_PROXY_FACETS'

ORGANIZATION_SQL = text("""
SELECT id, name, title, type, state
  FROM public."group"
 WHERE id = :organization OR name = :organization
 LIMIT 1
""")

MOLECULES_FOR_ORGANIZATION_SQL = text("""
WITH active_datasets AS (
    SELECT id, name
      FROM package
     WHERE owner_org = :organization_id
       AND type = 'dataset'
       AND state = 'active'
), related_identifiers AS (
    SELECT relationship.object_id AS identifier
      FROM relationship_relationship AS relationship
      JOIN active_datasets AS dataset
        ON relationship.subject_id IN (dataset.id, dataset.name)
     WHERE relationship.relation_type = 'related_to'
    UNION
    SELECT relationship.subject_id AS identifier
      FROM relationship_relationship AS relationship
      JOIN active_datasets AS dataset
        ON relationship.object_id IN (dataset.id, dataset.name)
     WHERE relationship.relation_type = 'related_to'
)
SELECT DISTINCT molecule.id, molecule.name
  FROM package AS molecule
  JOIN related_identifiers AS related
    ON related.identifier IN (molecule.id, molecule.name)
 WHERE molecule.type = 'molecule'
   AND molecule.state = 'active'
 ORDER BY molecule.id
""")


class MoleculeProxyReindexError(click.ClickException):
    """A concise, user-facing maintenance command error."""


def _concise_errors(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except click.ClickException:
            raise
        except Exception as exception:
            raise click.ClickException(
                'Maintenance command failed: %s' % exception)
    return wrapped


def _utc_timestamp():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _expected_proxy(organization_dict, organization_name):
    # Imported lazily because plugin.py registers this command module.
    from ckanext.relationship.plugin import _normalize_proxy_value
    return _normalize_proxy_value(
        organization_dict.get('title') or organization_name)


def _load_active_organization(session, organization_reference):
    """Resolve an active organization by UUID or name without CKAN actions."""
    row = session.execute(
        ORGANIZATION_SQL,
        {'organization': organization_reference}).fetchone()
    if row is None:
        raise MoleculeProxyReindexError(
            'Organization %s was not found.' % organization_reference)

    organization = {
        'id': row[0],
        'name': row[1],
        'title': row[2],
        'type': row[3],
        'state': row[4],
    }
    if organization['type'] != 'organization':
        raise MoleculeProxyReindexError(
            '%s is not an organization.' % organization_reference)
    if organization['state'] != 'active':
        raise MoleculeProxyReindexError(
            'Organization %s is not active.' % organization_reference)
    return organization


def _select_molecules(organization_id, session=None):
    """Select active related molecules with one read-only SQL statement."""
    session = session or model.Session
    rows = session.execute(
        MOLECULES_FOR_ORGANIZATION_SQL,
        {'organization_id': organization_id}).fetchall()
    molecules = {}
    for row in rows:
        molecule_id = row[0]
        if molecule_id not in molecules:
            molecules[molecule_id] = {
                'id': molecule_id,
                'name': row[1],
            }
    return [molecules[key] for key in sorted(molecules)]


def _audit_record(molecule, organization_name, status, expected_proxy,
                  error=None, previous_proxy=None):
    return {
        'molecule_id': molecule.get('id'),
        'molecule_name': molecule.get('name'),
        'organization_name': organization_name,
        'status': status,
        'previous_proxy': previous_proxy,
        'expected_canonical_proxy': expected_proxy,
        'error': error,
        'timestamp': _utc_timestamp(),
    }


def _write_record(handle, record):
    line = json.dumps(record, sort_keys=True)
    if handle is None:
        click.echo(line)
    else:
        handle.write(line + '\n')
        handle.flush()


@click.group(name='relationship')
def relationship():
    """Maintain relationship-derived data."""


@relationship.command(name='reindex-organization-proxy')
@click.option('--organization', required=True,
              help='Active organization name or ID.')
@click.option('--dry-run', is_flag=True,
              help='Validate and list selected molecules without Solr writes.')
@click.option('--apply', 'apply_changes', is_flag=True,
              help='Reindex the selected molecule documents.')
@click.option('--expected-molecules', type=click.IntRange(min=0))
@click.option('--audit-log', type=click.Path(dir_okay=False, writable=True))
@click.option('--confirm')
@_concise_errors
def reindex_organization_proxy(organization, dry_run, apply_changes,
                               expected_molecules, audit_log, confirm):
    """Reindex molecule proxy facets selected from PostgreSQL truth."""
    if dry_run == apply_changes:
        raise click.UsageError('Require exactly one of --dry-run or --apply.')
    if apply_changes:
        if expected_molecules is None:
            raise click.UsageError('--apply requires --expected-molecules.')
        if not audit_log:
            raise click.UsageError('--apply requires --audit-log.')
        if confirm != CONFIRMATION:
            raise click.UsageError(
                '--apply requires --confirm %s.' % CONFIRMATION)

    try:
        organization_dict = _load_active_organization(
            model.Session, organization)
        organization_id = organization_dict['id']
        organization_name = organization_dict['name']
        expected_proxy = _expected_proxy(
            organization_dict, organization_name)
        molecules = _select_molecules(organization_id)
    except click.ClickException:
        raise
    except Exception as exception:
        raise click.ClickException(
            'Unable to select molecules for organization %s: %s' %
            (organization, exception))

    if apply_changes and len(molecules) != expected_molecules:
        raise click.ClickException(
            'Selected %d molecules; expected %d. No documents were reindexed.' %
            (len(molecules), expected_molecules))

    reindexed = 0
    failed = 0
    audit_handle = None
    try:
        if audit_log:
            audit_handle = open(audit_log, 'a')
        for selected in molecules:
            if dry_run:
                _write_record(audit_handle, _audit_record(
                    selected, organization_name, 'validated', expected_proxy))
                continue

            molecule = selected
            error = None
            status = 'reindexed'
            try:
                molecule = tk.get_action('package_show')(
                    {'ignore_auth': True}, {'id': selected['id']})
                if (molecule.get('type') != 'molecule' or
                        molecule.get('state', 'active') != 'active'):
                    raise ValueError('Package is no longer an active molecule')
                rebuild(molecule['id'])
                reindexed += 1
            except Exception as exception:
                status = 'failed'
                error = str(exception)
                failed += 1
            _write_record(audit_handle, _audit_record(
                molecule, organization_name, status, expected_proxy,
                error=error))
    finally:
        if audit_handle is not None:
            audit_handle.close()

    click.echo('organization=%s selected=%d reindexed=%d failed=%d '
               'database_changed=false' % (
                   organization_name, len(molecules), reindexed, failed))


def get_commands():
    return [relationship]
