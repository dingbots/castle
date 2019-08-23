#!/usr/bin/xonsh

for k, v in sorted(${...}.items()):
    print(k, ":", repr(v))
