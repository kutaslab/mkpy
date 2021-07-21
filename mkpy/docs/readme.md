To start over and rebuild mkpy API docs from scratch with sphinx-apidoc 

* from the `docs` dir run this to generate docs from docstrings
```
sphinx-apidoc -f -e -o api_source .. test/*
```

Then tune up the top-level index.rst, and HandEdited.rst files to make
the docs look right.


