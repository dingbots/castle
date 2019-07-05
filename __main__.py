import pulumi
from putils import opts, FauxOutput
from staticsite import StaticSite
from levents import Package
from pulumi_aws import route53

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

p = Package(
    'SpamPack',
    sourcedir='spam',
)

pulumi.export('website',  site.url)
