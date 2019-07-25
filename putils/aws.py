import os

import pulumi
__all__ = 'get_region',


class NoRegionError:
    """
    Raised if we aren't able to detect the current region
    """


def get_region(resource):
    """
    Gets the AWS region for a given resource.
    """
    provider = resource.get_provider('aws::')
    config = pulumi.Config("aws").get('region')
    if provider and provider.region:
        return provider.region
    # These are stolen out of pulumi-aws
    elif config:
        return config
    elif 'AWS_REGION' in os.environ:
        return os.environ['AWS_REGION']
    elif 'AWS_DEFAULT_REGION' in os.environ:
        return os.environ['AWS_DEFAULT_REGION']
    else:
        raise NoRegionError("Unable to determine AWS Region")
