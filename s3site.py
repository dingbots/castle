import json
import mimetypes
import os

from pulumi import FileAsset
from pulumi_aws import s3

from utils import component


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
def StaticSite(name, domain, content_dir, __opts__):
    web_bucket = s3.Bucket(f'{name}-contents', website={
        "index_document": "index.html"
    })

    # FIXME: Recursive
    for file in os.listdir(content_dir):
        filepath = os.path.join(content_dir, file)
        mime_type, _ = mimetypes.guess_type(filepath)
        s3.BucketObject(f'{name}-{file}',
            bucket=web_bucket.id,
            source=FileAsset(filepath),
            content_type=mime_type)

    bucket_name = web_bucket.id
    s3.BucketPolicy(f"{name}-policy",
        bucket=bucket_name,
        policy=bucket_name.apply(public_read_policy_for_bucket))

    # FIXME: Register domain

    return {
        'bucket_id': web_bucket.id,
        'bucket_url': web_bucket.website_endpoint,
    }
