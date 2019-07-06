"""
Thing to generate the resources for an API Gateway and its routing table.
"""
from pulumi_aws import lambda_
from putils import opts, task, Component


class RoutingGateway(Component):
    def set_up(self, __name__, *, __opts__):
        self.__name = __name__

    def __enter__(self):
        self._table = RoutingTable(self, self.__name)
        return self._table

    def __exit__(self, type, value, traceback):
        if type or value or traceback:
            return

        @task
        async def buildtable():
            for entry in self._table.routes:
                method, path, package, lfunc = await entry.future()

        buildtable()


class RoutingTable:
    def __init__(self, gateway, name):
        self.gateway = gateway
        self.routes = list()
        self.__name = name

    def _add_entry(self, method, path, package, func, lambdaopts):
        @package.funcargs.apply
        def routebuilder(funcargs):
            lfunc = lambda_.Function(
                f'{self.__name}',
                handler=func,
                **funcargs,
                **opts(parent=self.gateway),
                **lambdaopts,
            )
            return method, path, package, lfunc
        self.routes.append(routebuilder)

    def get(self, path, package, func, **lambdaopts):
        self._add_entry('GET', path, package, func, lambdaopts)

    def post(self, path, package, func, **lambdaopts):
        self._add_entry('POST', path, package, func, lambdaopts)
