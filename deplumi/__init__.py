"""
Wrapper to connect resources to lambda calls.
"""
from pathlib import Path
import os

import pulumi
from pulumi_aws import (
    s3, apigateway, lambda_, route53
)

from putils import (
    opts, Component, component, outputish, get_region, Certificate, a_aaaa
)

from .builders.pipenv import PipenvPackage
from .resourcegen import ResourceGenerator
from .rolegen import generate_role

__all__ = 'Package', 'EventHandler', 'AwsgiHandler',

# Requirements:
#  * EventHandler(resource, event, package, func)
#    - Wires up the function (in the package) to an event on a specific resource
#  * Package(sourcedir, resources)
#    - Does pipenv-based dependencies
#    - Manages the build process to produce a bundle for lambda
#    - A single package may contain multiple bundles
#    - Generates roles to access the given resources
#    - Generates code in the package to instantiate resources.

_lambda_buckets = {}


def get_lambda_bucket(region=None, resource=None):
    """
    Gets the shared bucket for lambda packages for the given region
    """
    if resource is not None:
        region = get_region(resource)

    if region not in _lambda_buckets:
        _lambda_buckets[region] = s3.Bucket(
            f'lambda-bucket-{region}',
            region=region,
            versioning={
                'enabled': True,
            },
            # FIXME: Life cycle rules for expiration
            **opts(region=region),
        )

    return _lambda_buckets[region]


@outputish
async def build_zip_package(sourcedir, resgen):
    sourcedir = Path(sourcedir)
    if (sourcedir / 'Pipfile').is_file():
        package = PipenvPackage(sourcedir, resgen)
    else:
        raise OSError("Unable to detect package type")

    # Do any preparatory stuff
    await package.warmup()

    # Actually build the zip
    bundle = await package.build()

    return pulumi.FileAsset(os.fspath(bundle))


class Package(Component, outputs=['funcargs', 'bucket', 'object', 'role', '_resources']):
    def set_up(self, name, *, sourcedir, resources=None, __opts__):
        if resources is None:
            resources = {}
        resgen = ResourceGenerator(resources)
        bucket = get_lambda_bucket(resource=self)
        bobj = s3.BucketObject(
            f'{name}-code',
            bucket=bucket.id,
            source=build_zip_package(sourcedir, resgen),
            **opts(parent=self),
        )

        role = generate_role(
            f'{name}-role',
            {
                rname: (res, ...)  # Ask for basic RW permissions (not manage)
                for rname, res in resources.items()
            },
            **opts(parent=self)
        )

        return {
            'bucket': bucket,
            'object': bobj,
            'role': role,
            '_resources': list(resources.values()),  # This should only be used internally
        }

    def function(self, name, func, **kwargs):
        func = func.replace(':', '.')
        return lambda_.Function(
            f'{name}',
            handler=func,
            s3_bucket=self.bucket.bucket,
            s3_key=self.object.key,
            s3_object_version=self.object.version_id,
            runtime='python3.7',
            role=self.role.arn,
            **kwargs,
        )


@component(outputs=[])
def EventHandler(self, name, resource, event, package, func, __opts__):
    """
    Define a handler to process an event produced by a resource
    """
    ...


@component(outputs=[])
def AwsgiHandler(self, name, zone, domain, package, func, __opts__, **lambdaargs):
    """
    Define a handler to accept requests, using awsgi
    """
    func = package.function(f"{name}-function", func, **lambdaargs, **opts(parent=self))

    @func.arn.apply
    def lambdapath(arn):
        return f"arn:aws:apigateway:{get_region(self)}:lambda:path/2015-03-31/functions/{arn}/invocations"

    api = apigateway.RestApi(
        f"{name}-api",
        endpoint_configuration={
            'types': 'REGIONAL',
        },
        **opts(parent=self)
    )

    resource = apigateway.Resource(
        f"{name}-resource",
        rest_api=api,
        path_part="{proxy+}",
        parent_id=api.root_resource_id,
        **opts(parent=self)
    )

    method = apigateway.Method(
        f"{name}-method",
        rest_api=api,
        resource_id=resource.id,
        http_method="ANY",
        authorization="NONE",
        **opts(parent=self)
    )

    integration = apigateway.Integration(
        f"{name}-integration",
        rest_api=api,
        resource_id=resource.id,
        http_method="ANY",
        type="AWS_PROXY",
        integration_http_method="POST",
        passthrough_behavior="WHEN_NO_MATCH",
        uri=lambdapath,
        **opts(parent=self, depends_on=[method])
    )

    deployment = apigateway.Deployment(
        f"{name}-deployment",
        rest_api=api,
        stage_name=pulumi.get_stack(),
        **opts(depends_on=[integration], parent=self)
    )

    cert = Certificate(
        f"{name}-cert",
        domain=domain,
        zone=zone,
        **opts(parent=self)
    )

    domainname = apigateway.DomainName(
        f"{name}-domain",
        domain_name=domain,
        regional_certificate_arn=cert.cert_arn,
        # security_policy="TLS_1_2",
        endpoint_configuration={
            'types': 'REGIONAL',
        },
        **opts(parent=self)
    )

    bpm = apigateway.BasePathMapping(
        f"{name}-mapping",
        rest_api=api,
        domain_name=domain,
        stage_name=deployment.stage_name,
        **opts(depends_on=[deployment, domainname], parent=self)
    )

    a_aaaa(
        f"{name}-record",
        name=domain,
        zone_id=zone.zone_id,
        aliases=[
            {
                'name': domainname.regional_domain_name,
                'zone_id': domainname.regional_zone_id,
                'evaluate_target_health': True,
            },
        ],
        **opts(parent=self),
    )
