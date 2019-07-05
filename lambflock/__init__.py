"""
Wrapper to connect resources to lambda calls.
"""
from pathlib import Path
import os

import pulumi
from pulumi_aws import s3

from putils import opts, component, get_provider_for_region, outputish

from .builders.pipenv import PipenvPackage

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
async def build_zip_package(sourcedir):
    sourcedir = Path(sourcedir)
    if (sourcedir / 'Pipfile').is_file():
        package = PipenvPackage(sourcedir)
    else:
        raise OSError("Unable to detect package type")

    # Do any preparatory stuff
    await package.warmup()

    # Actually build the zip
    bundle = await package.build()

    return pulumi.FileAsset(os.fspath(bundle))


@component(outputs=[])
def Package(self, name, *, sourcedir, resources=None, __opts__):
    bucket = get_lambda_bucket(__opts__=__opts__)
    s3.BucketObject(
        f'{name}-code',
        bucket=bucket.id,
        source=build_zip_package(sourcedir),
        **opts(parent=self),
    )
    # TODO: Generate role based on resources referenced
    # NOTE: The role is also based on any EventHandler() declared
