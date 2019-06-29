import pulumi
from utils import opts
from s3site import StaticSite

# Create an AWS resource (S3 Bucket)
site = StaticSite('MainSite',
    domain='dingbots.dev',
    content_dir='www',
    **opts(),
)

# Export the name of the bucket
pulumi.export('website',  site.bucket_url)
