"""
Wrapper to connect resources to lambda calls.
"""
import hashlib
from pathlib import Path
import sys
import asyncio
import os
import subprocess
import zipfile

import pulumi
from pulumi_aws import s3

from utils import opts, component, get_provider_for_region, background, outputish

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


class PipenvPackage:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @property
    def pipfile(self):
        return self.root / 'Pipfile'

    @property
    def lockfile(self):
        return self.root / 'Pipfile.lock'

    @background
    def get_builddir(self):
        # FIXME: Linux only
        # FIXME: Caching
        buildroot = Path('/tmp/levents')
        buildroot.mkdir(parents=True, exist_ok=True)
        contents = self.lockfile.read_bytes()
        dirname = hashlib.sha3_256(contents).hexdigest()
        return buildroot / dirname

    async def _call_subprocess(self, *cmd, check=True, **opts):
        cmd = [
            os.fspath(part) if hasattr(part, '__fspath__') else part
            for part in cmd
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, **opts)
        stdout, stderr = await proc.communicate()
        if check and proc.returncode != 0:
            raise subprocess.SubprocessError
        return stdout, stderr

    async def _call_python(self, *cmd, **opts):
        return await self._call_subprocess(sys.executable, *cmd, **opts)

    async def _call_pipenv(self, *cmd, **opts):
        env = {
            'PIPENV_NOSPIN': '1',
            'PIPENV_PIPFILE': str(self.pipfile),
            'PIPENV_VIRTUALENV': await self.get_builddir(),
            **os.environ,
        }
        return await self._call_subprocess(
            'pipenv', *cmd,
            env=env,
            cwd=str(self.root),
            **opts,
        )

    async def warmup(self):
        """
        Do pre-build prep
        """
        builddir = await self.get_builddir()
        pulumi.debug(f"Using build dir {builddir}")
        if not builddir.exists():
            await self._call_python('-m', 'venv', builddir)

        if pulumi.runtime.is_dry_run():
            # Only do this on preview. Don't fail an up for this.
            await self._call_pipenv('check')

    async def build(self):
        """
        Actually build
        """
        builddir = await self.get_builddir()
        # FIXME: Actually compute this
        ziproot = builddir / 'lib' / 'python3.7' / 'site-packages'

        dest = builddir / 'bundle.zip'

        await self._real_build(builddir, ziproot, dest)

        return dest

    @background
    def _real_build(self, builddir, ziproot, dest):
        with zipfile.ZipFile(dest, 'w') as zf:
            ...
            # TODO: Build archive
            # 1. Recursively copy ziproot into dest
            # 2. Recursively copy self.root into dest


@outputish
async def build_zip_package(sourcedir):
    sourcedir = Path(sourcedir)
    if (sourcedir / 'Pipfile').is_file():
        package = PipenvPackage(sourcedir)
    else:
        raise OSError("Unable to detect package type")

    # Do any preperatory stuff
    await package.warmup()

    # Actually build the zip
    bundle = await package.build()

    return pulumi.FileAsset(os.fspath(bundle))


@component(outputs=[])
def Package(self, name, *, sourcedir, resources=(), __opts__):
    bucket = get_lambda_bucket(__opts__=__opts__)
    s3.BucketObject(
        f'{name}-code',
        bucket=bucket.id,
        source=build_zip_package(sourcedir),
        **opts(parent=self),
    )
