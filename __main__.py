import pulumi
from putils import opts, FauxOutput
from staticsite import StaticSite
from deplumi import Package, RoutingGateway
from pulumi_aws import route53, s3

config = pulumi.Config('castle')

zone = FauxOutput(route53.get_zone(name='dingbots.dev'))

# Create an AWS resource (S3 Bucket)
site = StaticSite(
    'MainSite',
    domain=config.require('domain'),
    zone=zone,
    content_dir='www',
    **opts(),
)

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

with RoutingGateway('ApiService') as routes:
    routes.get('/', spam, 'eggs:main')


pulumi.export('website',  site.url)
