import pulumi
from putils import opts
from deplumi import Package, AwsgiHandler
from pulumi_aws import route53

config = pulumi.Config('castle')

zone = route53.get_zone(name='dingbots.dev')

clank = Package(
    'Clank',
    sourcedir='clank',
    resources={
    },
    **opts()
)

api_domain = f'api.{config.require("domain")}'

AwsgiHandler(
    'ClankService',
    domain=api_domain,
    zone=zone,
    package=clank,
    func='__main__:main',
    environment={
        'variables': {
            'github_client_id': config.get('github-client-id'),  # OAuth Client ID
            'github_client_secret': config.get('github-client-secret'),  # OAuth Client Secret
            'github_app_id': config.get('github-app-id'),  # Numeric App ID
            'github_private_key': config.get('github-private-key'),  # Signs JWTs for API authn
            'github_secret': config.get('github-secret'),  # github->app hook verify
        },
    },
    **opts()
)

pulumi.export('webhook_url',  f"https://{api_domain}/postreceive")
