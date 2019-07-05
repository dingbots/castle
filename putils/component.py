"""
Decorator to deal with the very annoying and grossly incomplete
ComponentResource boilerplate.
"""

import pulumi
import asyncio

from .paio import FauxOutput, task, unwrap


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
            # Build out the declared outputs so they're available immediately
            for name in outputs:
                futures[name] = asyncio.get_event_loop().create_future()
                # FIXME: Use real Outputs instead of FauxOutputs
                setattr(self, name, FauxOutput(futures[name]))

            @task
            async def inittask():
                # Wraps up the initialization function and marshalls the data around
                try:
                    # Call the initializer
                    outs = await unwrap(func(self, __name__, *pargs, __opts__=__opts__, **kwargs))
                except Exception as e:
                    # Forward the exception to the futures, so they don't hang
                    for f in futures.values():
                        f.set_exception(e)
                    raise
                else:
                    # Process the returned outputs
                    if outs is None:
                        outs = {}
                    self.register_outputs(outs)
                    for name, value in outs.items():
                        if name in futures:
                            futures[name].set_result(value)
                        else:
                            setattr(self, name, value)

            inittask()

        klass = type(func.__name__, (pulumi.ComponentResource,), {
            '__init__': __init__,
            '__doc__': func.__doc__,
            '__module__': func.__module__,
            '__qualname__': func.__qualname__,
        })
        return klass

    return _
