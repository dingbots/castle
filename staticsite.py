import json
import mimetypes
from pathlib import Path

from pulumi import FileAsset
from pulumi_aws import s3, route53, acm, cloudfront

from putils import component, opts


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


def walk(starting):
    """
    Return all files under this directory, recursively
    """
    starting = Path(starting).absolute()
    for p in starting.glob('**/*'):
        absp = p.absolute()
        relp = absp.relative_to(starting)
        yield absp, relp


@component(outputs=['cert', 'cert_arn'])
def Certificate(self, name, domain, zone, __opts__):
    """
    Gets a TLS certifcate for the given domain, using ACM and DNS validation.

    This will be in us-east-1, suitable for CloudFront
    """
    cert = acm.Certificate(
        f"{name}-certificate",
        domain_name=domain,
        validation_method="DNS",
        **opts(parent=self, region='us-east-1'),
    )

    # TOOD: Multiple DVOs
    dvo = cert.domain_validation_options[0]
    record = route53.Record(
        f"{name}-validation-record",
        name=dvo['resourceRecordName'],
        zone_id=zone.zone_id,
        type=dvo['resourceRecordType'],
        records=[dvo['resourceRecordValue']],
        ttl=10*60,  # 10 minutes
        **opts(parent=self),
    )

    validation = acm.CertificateValidation(
        f"{name}-validation",
        certificate_arn=cert.arn,
        validation_record_fqdns=[record.fqdn],
        **opts(parent=self, region="us-east-1"),
    )

    return {
        'cert': cert,
        'cert_arn': validation.certificate_arn,
    }


@component(outputs=['url'])
def StaticSite(self, name, domain, zone, content_dir, __opts__):
    """
    A static site, at the given domain with the contents of the given directory.

    Uses S3, CloudFront, ACM, and Route53.
    """
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

    for absp, relp in walk(content_dir):
        mime_type, _ = mimetypes.guess_type(str(absp))
        s3.BucketObject(
            f'{name}-{relp!s}',
            key=str(relp),
            bucket=web_bucket.id,
            source=FileAsset(str(absp)),
            content_type=mime_type,
            **opts(parent=web_bucket),
        )

    bucket_name = web_bucket.id
    s3.BucketPolicy(
        f"{name}-policy",
        bucket=bucket_name,
        policy=bucket_name.apply(public_read_policy_for_bucket),
        **opts(parent=web_bucket),
    )

    cert = Certificate(
        f"{name}-cert",
        domain=domain,
        zone=zone,
        **opts(parent=self),
    )

    distro = cloudfront.Distribution(
        f"{name}-dist",
        enabled=True,
        # Alternate aliases the CloudFront distribution can be reached at, in addition to https://xxxx.cloudfront.net.
        # Required if you want to access the distribution via config.targetDomain as well.
        aliases=[domain],

        is_ipv6_enabled=True,

        # We only specify one origin for this distribution, the S3 content bucket.
        origins=[
            {
                "originId": web_bucket.arn,
                "domainName": web_bucket.website_endpoint,
                "customOriginConfig": {
                    # Amazon S3 doesn't support HTTPS connections when using an S3 bucket configured as a website endpoint.
                    "originProtocolPolicy": "http-only",
                    "httpPort": 80,
                    "httpsPort": 443,
                    "originSslProtocols": ["TLSv1.2"],
                },
            },
        ],

        default_root_object="index.html",

        # A CloudFront distribution can configure different cache behaviors based on the request path.
        # Here we just specify a single, default cache behavior which is just read-only requests to S3.
        default_cache_behavior={
            "targetOriginId": web_bucket.arn,

            "viewerProtocolPolicy": "redirect-to-https",
            "allowedMethods": ["GET", "HEAD", "OPTIONS"],
            "cachedMethods": ["GET", "HEAD", "OPTIONS"],

            "forwardedValues": {
                "cookies": {"forward": "none"},
                "queryString": False,
            },

            "minTtl": 0,
            "defaultTtl": 10*60,
            "maxTtl": 10*60,
        },

        # "All" is the most broad distribution, and also the most expensive.
        # "100" is the least broad, and also the least expensive.
        price_class="PriceClass_100",

        # You can customize error responses. When CloudFront recieves an error from the origin (e.g.
        # S3 or some other web service) it can return a different error code, and return the
        # response for a different resource.
        custom_error_responses=[
            {"errorCode": 404, "responseCode": 404, "responsePagePath": "/404.html"},
        ],

        restrictions={
            "geoRestriction": {
                "restrictionType": "none",
            },
        },

        viewer_certificate={
            "acmCertificateArn": cert.cert_arn,
            "sslSupportMethod": "sni-only",
        },

        # loggingConfig: {
        #     bucket: logsBucket.bucketDomainName,
        #     includeCookies: false,
        #     prefix: `${config.targetDomain}/`,
        # },
        **opts(parent=self),
    )

    route53.Record(
        f"{name}-record-a",
        name=domain,
        zone_id=zone.zone_id,
        type='A',
        aliases=[
            {
                'name': distro.domain_name,
                'zone_id': distro.hosted_zone_id,
                'evaluate_target_health': True,
            },
        ],
        **opts(parent=self),
    )

    route53.Record(
        f"{name}-record-aaaa",
        name=domain,
        zone_id=zone.zone_id,
        type='AAAA',
        aliases=[
            {
                'name': distro.domain_name,
                'zone_id': distro.hosted_zone_id,
                'evaluate_target_health': True,
            },
        ],
        **opts(parent=self),
    )

    return {
        'url': f'https://{domain}/'
    }
