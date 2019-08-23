#!/usr/bin/xonsh
source /etc/xonshrc

for pipfile in [p.absolute() for p in pg`**/Pipfile`]:
    cd @(pipfile.parent)
    print("")
    print(f"Checking {$PWD}")
    pipenv check
