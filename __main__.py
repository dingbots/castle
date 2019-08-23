import pulumi
from putils import opts, FauxOutput
from deplumi import Package, AwsgiHandler
from pulumi_aws import route53, s3

config = pulumi.Config('castle')

zone = FauxOutput(route53.get_zone(name='dingbots.dev'))

buf = s3.Bucket(
    'MyBucket',
    **opts(),
)

spam = Package(
    'SpamPack',
    sourcedir='spam',
    resources={
        'buffer': buf,
    }
)

api_domain = f'api.{config.require("domain")}'

AwsgiHandler(
    'SpamService',
    domain=api_domain,
    zone=zone,
    package=spam,
    func='__main__:main',
)

pulumi.export('website',  site.url)
pulumi.export('api_url',  f"https://{api_domain}/")
