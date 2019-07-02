import pulumi
import pulumi_aws
import os
import inspect
import asyncio
import functools


PROVIDER = None

if os.environ.get('STAGE') == 'local':
    PROVIDER = pulumi_aws.Provider(
        "localstack",
        skip_credentials_validation=True,
        skip_metadata_api_check=True,
        s3_force_path_style=True,
        access_key="mockAccessKey",
        secret_key="mockSecretKey",
        region='us-east-1',
        endpoints=[{
            'apigateway': "http://localhost:4567",
            'cloudformation': "http://localhost:4581",
            'cloudwatch': "http://localhost:4582",
            'cloudwatchlogs': "http://localhost:4586",
            'dynamodb': "http://localhost:4569",
            # "DynamoDBStreams": "http://localhost:4570",
            # "Elasticsearch": "http://localhost:4571",
            'es': "http://localhost:4578",
            'firehose': "http://localhost:4573",
            'iam': "http://localhost:4593",
            'kinesis': "http://localhost:4568",
            'kms': "http://localhost:4584",
            'lambda': "http://localhost:4574",
            'redshift': "http://localhost:4577",
            'route53': "http://localhost:4580",
            's3': "http://localhost:4572",
            'ses': "http://localhost:4579",
            # "StepFunctions": "http://localhost:4585",
            'sns': "http://localhost:4575",
            'sqs': "http://localhost:4576",
            'ssm': "http://localhost:4583",
            'sts': "http://localhost:4592",
        }],
    )


def opts(**kwargs):
    """
    Defines an __opts__ for resources, including any localstack config.

    localstack config is only applied if this is a top-level component (does not
    have a parent).

    Usage:
    >>> Resource(..., **opts(...))
    """
    if PROVIDER is not None and 'parent' not in kwargs:
        kwargs['provider'] = PROVIDER
    return {
        '__opts__': pulumi.ResourceOptions(**kwargs)
    }


def component(namespace=None):
    """
    Makes the given callable a component, with much less boilerplate.

    If no namespace is given, uses the module and function names

    @component('pkg:MyResource')
    def MyResource(self, name, ..., __opts__):
        ...
        return {...outputs}
    """
    def _(func):
        nonlocal namespace
        if namespace is None:
            namespace = f"{func.__module__.replace('.', ':')}:{func.__name__}"

        def __init__(self, name, *pargs, __opts__=None, **kwargs):
            super(klass, self).__init__(namespace, name, None, __opts__)
            outputs = func(self, name, *pargs, __opts__=__opts__, **kwargs)
            if outputs:
                # TOOD: Filter for just the outputs
                self.register_outputs(outputs)
                vars(self).update(outputs)

        klass = type(func.__name__, (pulumi.ComponentResource,), {
            '__init__': __init__,
            '__doc__': func.__doc__,
        })
        return klass

    return _


def mkfuture(val):
    if inspect.isawaitable(val):
        return asyncio.ensure_future(val)
    else:
        f = asyncio.get_event_loop().create_future()
        f.set_result(val)
        return f


def and_then(awaitable):
    """
    Chain together coroutines
    """
    # Don't like turning these into tasks, but there's some kind of multi-await
    # going on inside pulumi
    awaitable = mkfuture(awaitable)

    def _(func):

        @functools.wraps(func)
        async def wrapper():
            value = await awaitable
            rv = mkfuture(func(value))
            return await rv

        return mkfuture(wrapper())

    return _
