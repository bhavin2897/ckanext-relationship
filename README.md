[![Tests](https://github.com//ckanext-relationship/workflows/Tests/badge.svg?branch=main)](https://github.com//ckanext-relationship/actions)

### forked from [DataShades/ckanext-relationship](https://github.com/DataShades/ckanext-relationship)
####Version Tag from forked v0.1.8

# ckanext-relationship

The extension adds an additional table to the database that stores relationships between entities in the form of triples (subject_id, object_id, relation_type). The relation_type parameter sets the type of relationship: peer-to-peer (related_to <=> related_to) and subordinate (child_of <=> parent_of). Adding, deleting and getting a list of relationships between entities is carried out using actions (relation_create, relation_delete, relations_list). The description of the types of relationships between entities is carried out in the entity schema in the form:
```
- field_name: related_projects
  label: Related Projects
  preset: related_entity
  current_entity: package
  current_entity_type: dataset
  related_entity: package
  related_entity_type: project
  relation_type: related_to
  multiple: true
  updatable_only: false
  required: false
  
```
Entity (current_entity, related_entity) - one of three options: package, organization, group.

Entity type (current_entity_type, related_entity_type) - entity customized using ckanext-scheming.

Multiple - toggle the ability to add multiple related entities.

Updatable_only - toggle the ability to add only entities that can be updated by the current user.

## Requirements

**TODO:** For example, you might want to mention here which versions of CKAN this
extension works with.

If your extension works across different versions you can add the following table:

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.6 and earlier | not tested    |
| 2.7             | not tested    |
| 2.8             | not tested    |
| 2.9             | yes    |
|2.10  | no (please use latest version tag) |     


## Installation

To install ckanext-relationship:

1. Activate your CKAN virtual environment, for example:

    ``` . /usr/lib/ckan/default/bin/activate ```

2. Clone the source and install it on the virtualenv
```
    git clone https://github.com//ckanext-relationship.git
    cd ckanext-relationship
    pip install -e .
    pip install -r requirements.txt
```

3. Add `relationship` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

```     sudo service apache2 reload ``` 


5. To Migrate database tables
```
ckan -c /etc/ckan/default/ckan.ini db upgrade -p relationship
```
This creates a new database table within CKAN, to store new field_name of relation_entity and their types. 


## Config settings

None at present

**TODO:** Document any optional config settings here. For example:

	# The minimum number of hours to wait before re-checking a resource
	# (optional, default: 24).
	ckanext.relationship.some_setting = some_default_value


## Developer installation

To install ckanext-relationship for development, activate your CKAN virtualenv and
do:

    git clone https://github.com//ckanext-relationship.git
    cd ckanext-relationship
    python setup.py develop
    pip install -r dev-requirements.txt


## Tests

To run the tests, do:

    pytest --ckan-ini=test.ini


## Releasing a new version of ckanext-relationship

If ckanext-relationship should be available on PyPI you can follow these steps to publish a new version:

1. Update the version number in the `setup.py` file. See [PEP 440](http://legacy.python.org/dev/peps/pep-0440/#public-version-identifiers) for how to choose version numbers.

2. Make sure you have the latest version of necessary packages:

    pip install --upgrade setuptools wheel twine

3. Create a source and binary distributions of the new version:

       python setup.py sdist bdist_wheel && twine check dist/*

   Fix any errors you get.

4. Upload the source distribution to PyPI:

       twine upload dist/*

5. Commit any outstanding changes:

       git commit -a
       git push

6. Tag the new release of the project on GitHub with the version number from
   the `setup.py` file. For example if the version number in `setup.py` is
   0.0.1 then do:

       git tag 0.0.1
       git push --tags

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
