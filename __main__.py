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
            'github-client-id': config.get('github-client-id'),
            'github-client-secret': config.get('github-client-secret'),
            'github-application-id': config.get('github-app-id'),
            'github-private-key': config.get('github-private-key'),
            'github-webhook-secret': config.get('github-secret'),  # Authenticates github->func
        }
    },
    **opts()
)

pulumi.export('webhook_url',  f"https://{api_domain}/postreceive")
