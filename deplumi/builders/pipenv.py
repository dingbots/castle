import asyncio
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pulumi

from putils import background


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
            'PIPENV_VERBOSITY': '-1',
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

        # TODO: Use `pipenv lock --requirements` to feed into `pip install --target`

    async def build(self):
        """
        Actually build
        """
        builddir = await self.get_builddir()
        # FIXME: Actually compute this
        ziproot = builddir / 'lib' / 'python3.7' / 'site-packages'

        dest = builddir / 'bundle.zip'

        await self._build_zip(dest, ziproot, builddir)

        return dest

    @background
    def _build_zip(self, dest, *dirs):
        with zipfile.ZipFile(dest, 'w') as zf:
            ...
            # TODO: Build archive
            # 1. Recursively copy ziproot into dest
            # 2. Recursively copy self.root into dest
            # - Ideally, don't include pip, setuptools, or pkg_resources unless specifically asked for
            #   (It would be Really Cool if pipenv grew a --target)
