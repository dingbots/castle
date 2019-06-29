import pulumi
import pulumi_aws
import os


PROVIDER = None

if os.environ.get('STAGE') == 'local' or True:
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

    Usage:
    >>> Resource(..., **opts(...))
    """
    if PROVIDER is not None:
        kwargs['provider'] = PROVIDER
    return {
        '__opts__': pulumi.ResourceOptions(**kwargs)
    }


def component(namespace):
    """
    Makes the given callable a component, with much less boilerplate

    @component('pkg:MyResource')
    def MyResource(name, ..., __opts__):
        ...
        return {...outputs}
    """
    def _(func):
        def __init__(self, name, *pargs, __opts__=None, **kwargs):
            super(klass, self).__init__(namespace, name, None, __opts__)
            outputs = func(name, *pargs, __opts__=__opts__, **kwargs)
            if outputs:
                # TOOD: Filter for just the outputs
                self.register_outputs(outputs)
                vars(self).update(outputs)

        klass = type(func.__name__, (pulumi.ComponentResource,), {
            '__init__': __init__,
        })
        return klass

    return _
