import pulumi
from utils import opts, and_then
from staticsite import StaticSite
from pulumi_aws import route53

zone = route53.get_zone(name='dingbots.dev')


@and_then(zone)
def zone_id(zone):
    return zone.zone_id


# Create an AWS resource (S3 Bucket)
site = StaticSite(
    'MainSite',
    domain='dingbots.dev',
    zone_id=zone_id,
    content_dir='www',
    **opts(),
)

# Export the name of the bucket
pulumi.export('website',  site.url)
# pulumi.export('nameservers', zone.name_servers)
