[![Tests](https://github.com//ckanext-relationship/workflows/Tests/badge.svg?branch=main)](https://github.com//ckanext-relationship/actions)

# ckanext-relationship

This extension provides a way to create relations between
different types of packages, organizations and groups.

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.6 and earlier | not tested    |
| 2.7             | not tested    |
| 2.8             | not tested    |
| 2.9             | yes           |

Suggested values:

* "yes"
* "not tested" - I can't think of a reason why it wouldn't work
* "not yet" - there is an intention to get it working
* "no"


## Installation

To install ckanext-relationship:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Clone the source and install it on the virtualenv

    git clone https://github.com//ckanext-relationship.git
    cd ckanext-relationship
    pip install -e .
	pip install -r requirements.txt

3. Add `relationship` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload


## Config settings

None at present

**TODO:** Document any optional config settings here. For example:

	# Set a limit of relationships for a dataset
	# (optional, default: 5).
	ckanext.relationship.max_relationship_number = 10


## Validators

A list of validators you could use in your schema:
    1. relationship_restrict_max_relationships
    The validator will restrict the amount of dataset that could be saved as
    a relationship. The default value is 5, but could be altered with a
    ckanext.relationship.max_relationship_number config option.

    0 (zero) means no limit.



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
