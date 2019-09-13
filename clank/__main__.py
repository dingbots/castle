import gqlmod
gqlmod.enable_gql_import()

import awsgi
import app


def main(event, context):
    rv = awsgi.response(app.app, event, context, base64_content_types={})
    return rv
