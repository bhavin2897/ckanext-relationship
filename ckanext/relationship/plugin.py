import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckanext.relationship.logic.action as action
import ckanext.relationship.logic.auth as auth
import ckanext.relationship.logic.validators as validators
import ckanext.relationship.helpers as helpers


class RelationshipPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)

    # IConfigurer
    def update_config(self, config_):
        tk.add_template_directory(config_, 'templates')
        tk.add_public_directory(config_, 'public')
        tk.add_resource('fanstatic', 'relationship')

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
