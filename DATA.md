Data Modeling
=============

github access needs a token, from an installation ID

events -> repo (in event data)
repo -> installation id (api call, cachable)
installation id -> token (api call, short lived)

repo -> PyPI tokens (test, prod, other)
