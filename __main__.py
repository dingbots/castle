import pulumi
from utils import opts, FauxOutput
from staticsite import StaticSite
from pulumi_aws import route53

zone = FauxOutput(route53.get_zone(name='dingbots.dev'))

# Create an AWS resource (S3 Bucket)
site = StaticSite(
    'MainSite',
    domain='dingbots.dev',
    zone=zone,
    content_dir='www',
    **opts(),
)

pulumi.export('website',  site.url)
