import ckan.plugins.toolkit as tk
from flask import Blueprint, jsonify


def get_blueprints():
    return [
        relationships,
    ]


relationships = Blueprint("relationships", __name__)


@relationships.route("/api/util/relationships/autocomplete")
def relationships_autocomplete():
    entity_type = "report"
    incomplete = tk.request.args.get("incomplete", "")
    result = []
    if incomplete:
        packages = tk.get_action('package_search')({}, {
            'q': incomplete,
            'fq': f'type:{entity_type}',
            'fl': 'id, title',
            'rows': 100,
            'include_private': True,
            "sort": 'score desc',
        })['results']

        filtered_packages = filter(
            lambda pkg: incomplete.lower() in pkg["title"].lower(), packages
        )
        result = {
            "ResultSet": {
                "Result": [
                    {
                        "name": pkg["id"],
                        "title": pkg["title"],
                    } for pkg in filtered_packages
                ]
            }
        }
    return jsonify(result)
