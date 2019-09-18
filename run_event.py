#!/usr/bin/env python3
"""
Dev Script

Runs the given event
"""
import functools
import json
import os
from pathlib import Path
import subprocess
import sys

# TODO: Make these arguments
PACKAGE = 'clank'
FUNCTION = '__main__:main'
EVENT = 'push'

PROJ_ROOT = Path(__file__).absolute().parent

def run(*pargs, venvdir=None, **kwargs):
    if 'env' not in kwargs:
        kwargs['env'] = dict(os.environ)
    if venvdir is None:
        kwargs['env'].pop('VIRTUAL_ENV', None)
    elif venvdir is ...:
        pass  # Let it fall through
    if venvdir is not None:
        kwargs['env']['VIRTUAL_ENV'] = str(venvdir)
        kwargs['env']['PATH'] = f"{venvdir}/bin:{kwargs['env']['PATH']}"
    return subprocess.run(*pargs, **kwargs)

@functools.lru_cache()
def get_venv(pkgname):
    """
    Get the venv directory for the given package.

    Transparently sets it up and syncs it.
    """
    # FIXME: Linux only
    venvdir = PROJ_ROOT / f'.{pkgname}-venv'
    pkgdir = PROJ_ROOT / pkgname

    if not venvdir.is_dir():
        run([sys.executable, '-m', 'venv', str(venvdir)], check=True)
        run(['pip', 'install', 'pipenv'], venvdir=venvdir, check=True)

    run(['pipenv', 'sync'], venvdir=venvdir, cwd=str(pkgdir), check=True)
    return venvdir

def get_event_path(pkgname, eventname):
    return PROJ_ROOT / f"{pkgname}_events" / f"{eventname}.lambda"

def pulumi_config():
    proc = run(
        ['pulumi', 'config', '--json', '--show-secrets'],
        stdout=subprocess.PIPE
    )
    data = json.loads(proc.stdout)
    return {
        key: stuff.get('value')
        for key, stuff in data.items()
    }

def load_environ():
    env = dict(os.environ)
    for key, value in pulumi_config().items():
        group, name = key.split(':', 1)
        if group != 'castle':
            continue

        env[name.replace('-', '_')] = value
    return env

def call_func(pkgname, funcname, eventname):
    venvdir = get_venv(pkgname)
    eventpath = get_event_path(PACKAGE, EVENT)
    module, function = funcname.split(':', 1)
    modulefile = PROJ_ROOT / pkgname / (module.replace('.', '/') + '.py')
    run(
        [
            'python', '-c',
            f"""
import json
import sys

module = dict(
    __name__="{module}",
    __file__="{modulefile}",
)
with open(module['__file__'], 'rt') as mf:
    code = compile(mf.read(), module['__file__'], 'exec')
    exec(code, module)

module["{function}"](json.load(sys.stdin), None)
""",
        ],
        venvdir=venvdir, stdin=eventpath.open('r'),
        cwd=str(PROJ_ROOT / pkgname), check=True, env=load_environ()
    )

def main():
    call_func(PACKAGE, FUNCTION, EVENT)

if __name__ == '__main__':
    main()
