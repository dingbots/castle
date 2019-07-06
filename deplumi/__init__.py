"""
Wrapper to connect resources to lambda calls.
"""
from pathlib import Path
import os

import pulumi
from pulumi_aws import s3, apigateway, lambda_

from putils import opts, Component, component, get_provider_for_region, outputish

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


def get_lambda_bucket(region=None, __opts__=None):
    """
    Gets the shared bucket for lambda packages for the given region
    """
    provider = None
    if __opts__ is not None:
        provider = getattr(__opts__, 'provider', None)
        pulumi.info(f"Found provider {provider}")

    if region not in _lambda_buckets:
        if provider is None and region is not None:
            pulumi.info(f"Given region is {region}")
            provider = get_provider_for_region(region)
            region = getattr(provider, 'region', None)
            pulumi.info(f"Calculated region is {region}")

        # FIXME: This doesn't handle the implicit case.

        _lambda_buckets[region] = s3.Bucket(
            f'lambda-bucket-{region}',
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
        bucket = get_lambda_bucket(__opts__=__opts__)
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
def AwsgiHandler(self, name, package, func, __opts__, **lambdaargs):
    """
    Define a handler to accept requests, using awsgi
    """
    func = package.function(f"{name}-function", func, **lambdaargs, **opts(parent=self))
    action = ...  # apigateway.Action, pointing to the lambda
    calling_role = ...  # iam.Role, allowing API Gateway to call the lambda
    integ = apigateway.Integration(
        f"{name}-integration",
        type='AWS_PROXY',
        http_method='ANY',
        # resource_id=TODO,
        # ui=action.arn,
        # credentials=calling_role.arn,
        **opts(parent=self)
    )
