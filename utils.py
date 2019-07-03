import pulumi
import pulumi_aws
import os
import inspect
import asyncio
import functools
import logging
import traceback

logger = logging.getLogger(__name__)


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

_provider_cache = {}


def get_provider_for_region(region):
    if PROVIDER is not None:
        # Using localstack
        return PROVIDER

    if region not in _provider_cache:
        _provider_cache[region] = pulumi_aws.Provider(
            region,
            # profile=pulumi_aws.config.profile, # FIXME
            region=region,
        )

    return _provider_cache[region]


def opts(*, region=None, **kwargs):
    """
    Defines an __opts__ for resources, including any localstack config.

    localstack config is only applied if this is a top-level component (does not
    have a parent).

    Usage:
    >>> Resource(..., **opts(...))
    """
    if PROVIDER is not None:
        # Using localstack
        if 'parent' not in kwargs:
            # Unless a parent is set, in which case lets use inheritance
            kwargs.setdefault('provider', PROVIDER)
    elif region is not None:
        assert 'provider' not in kwargs
        # Specified a specific region (and not using localstatck)
        kwargs['provider'] = get_provider_for_region(region)
    return {
        '__opts__': pulumi.ResourceOptions(**kwargs)
    }


def mkfuture(val):
    """
    Wrap the given value in a future (turn into a task).

    Intelligentally handles awaitables vs not.
    """
    if inspect.isawaitable(val):
        return asyncio.ensure_future(val)
    else:
        f = asyncio.get_event_loop().create_future()
        f.set_result(val)
        return f


async def unwrap(value):
    """
    Resolve all the awaitables, returing a simple value.
    """
    # This is to make sure awaitables boxing awaitables get handled.
    # This shouldn't happen in proper programs, but async can be hard.
    logger.debug("unwrap %r", value)
    while inspect.isawaitable(value):
        value = await value
        logger.debug("unwrap %r", value)
    return value


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
            value = unwrap(awaitable)
            rv = func(value)
            return await unwrap(rv)

        return mkfuture(wrapper())

    return _


def outputish(func):
    """
    Decorator to produce FauxOutputs on call
    """
    @functools.wraps(func)
    def wrapper(*pargs, **kwargs):
        return FauxOutput(func(*pargs, **kwargs))

    return wrapper


def task(func):
    async def runner(*pargs, **kwargs):
        try:
            await func(*pargs, **kwargs)
        except Exception:
            traceback.print_exc()
            pulumi.error(f"Error in {func}")

    @functools.wraps(func)
    def wrapper(*pargs, **kwargs):
        return asyncio.create_task(runner(*pargs, **kwargs))

    return wrapper


class FauxOutput:
    """
    Makes a coroutine a faux Output.
    """
    def __init__(self, coro):
        self._value = mkfuture(coro)

    @outputish
    async def __getitem__(self, key):
        """
        Shortcut to index the eventual value.
        """
        return (await self._value)[key]

    @outputish
    async def __getattr__(self, name):
        """
        Shortcut to get an attribute from the eventual value.
        """
        return getattr(await self._value, name)

    @outputish
    async def apply(self, func):
        """
        Eventually call the given function with the eventual value.
        """
        value = await unwrap(self._value)
        rv = func(value)
        return await unwrap(rv)

    def __await__(self):
        return self._value.__await__()


def component(namespace=None, outputs=()):
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

        def __init__(self, __name__, *pargs, __opts__=None, **kwargs):
            super(klass, self).__init__(namespace, __name__, None, __opts__)
            futures = {}
            logger.debug("Building outputs")
            for name in outputs:
                futures[name] = asyncio.get_event_loop().create_future()
                setattr(self, name, FauxOutput(futures[name]))

            @task
            async def inittask():
                logger.debug("calling init func %r", func)
                try:
                    outs = await unwrap(func(self, __name__, *pargs, __opts__=__opts__, **kwargs))
                except Exception as e:
                    for f in futures.values():
                        f.set_exception(e)
                    raise
                else:
                    logger.debug(f"processing outs {outs!r}")
                    if outs is None:
                        outs = {}
                    # TOOD: Filter for just the outputs
                    self.register_outputs(outs)
                    for name, value in outs.items():
                        if name in futures:
                            futures[name].set_result(value)
                        else:
                            setattr(self, name, value)

            logger.debug("starting task")
            inittask()

        klass = type(func.__name__, (pulumi.ComponentResource,), {
            '__init__': __init__,
            '__doc__': func.__doc__,
        })
        return klass

    return _
