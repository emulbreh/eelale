eelale
======

cross-compiles Python wheels inside containers.

Usage
------

.. code-block:: console

    # build wheel from a single package:
    $ eelale build gevent

    # or from a set of requirements:
    $ eelale build -r requirements.txt

    # build portable wheels (PEP 513)
    $ eelale build --policy manylinux1_x86_64 gevent

    # provide build dependencies via images:
    $ eelale build --image build-dependency-image psycopg2


Installation
-------------

Simply ``pip install eelale``. You also need Docker.
