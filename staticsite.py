import json
import mimetypes
import os

import pulumi
from pulumi import FileAsset
from pulumi_aws import s3, route53

from utils import component, opts


def public_read_policy_for_bucket(bucket_name):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket_name}/*",
            ]
        }]
    })


@component('pkg:S3Site')
def StaticSite(self, name, domain, zone_id, content_dir, __opts__):
    pulumi.log.info(f"Using domain {domain}")
    web_bucket = s3.Bucket(
        f'{name}-bucket',
        bucket=domain,
        website={
            "index_document": "index.html",
            "errorDocument": "404.html",
        },
        acl='public-read',
        website_domain=domain,
        **opts(parent=self),
    )

    # FIXME: Recursive
    for file in os.listdir(content_dir):
        filepath = os.path.join(content_dir, file)
        mime_type, _ = mimetypes.guess_type(filepath)
        s3.BucketObject(
            f'{name}-{file}',
            __name__=file,
            bucket=web_bucket.id,
            source=FileAsset(filepath),
            content_type=mime_type,
            **opts(parent=web_bucket),
        )

    bucket_name = web_bucket.id
    s3.BucketPolicy(
        f"{name}-policy",
        bucket=bucket_name,
        policy=bucket_name.apply(public_read_policy_for_bucket),
    )

    route53.Record(
        f"{name}-record",
        name=domain,
        zone_id=zone_id,
        type='A',
        aliases=[
            {
                'name': 's3-website.us-east-2.amazonaws.com',  # Don't seem to need a specific bucket?
                'zone_id': web_bucket.hosted_zone_id,
                'evaluate_target_health': True,
            },
        ],
        **opts(parent=self),
    )

    return {
        'bucket_id': web_bucket.id,
        'bucket_url': web_bucket.website_endpoint,
        'url': f'http://{domain}/'
    }
