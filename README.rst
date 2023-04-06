consolidatewheels
=================

.. image:: https://github.com/amol-/consolidatewheels/actions/workflows/tests.yml/badge.svg
    :target: https://github.com/amol-/consolidatewheels/actions/workflows/tests.yml

.. image:: https://coveralls.io/repos/amol-/consolidatewheels/badge.svg
    :target: https://coveralls.io/r/amol-/consolidatewheels

.. image:: https://img.shields.io/pypi/v/consolidatewheels.svg
   :target: https://pypi.python.org/pypi/consolidatewheels

.. image:: https://img.shields.io/pypi/pyversions/consolidatewheels.svg
    :target: https://pypi.python.org/pypi/consolidatewheels

.. image:: https://img.shields.io/pypi/l/consolidatewheels.svg
    :target: https://pypi.python.org/pypi/consolidatewheels

Introduction
------------

When multiple wheels depend on each other and share some ``.so`` files,
it is possible to rely on ``auditwheel --exclude`` to make sure the ``.so``
is included in only one of the wheels to avoid duplicating the file in every package.

That allows Python wheels to share the same ``.so`` as far as at least one of them
is loading them in memory. See https://github.com/pypa/auditwheel/issues/76 and
https://github.com/pypa/auditwheel/pull/368 for discussions on the topic.

The problem with this approach is that the package where the ``.so`` is included
will have the library name mangled by ``auditwheel``, while the ones where it's
excluded will reference to the library with its original name.

Suppose you have ``libone.whl`` and ``libtwo.whl`` both depending on ``libfoo.so``,
and ``libone`` is a dependency of ``libtwo`` so you already know you can include
``libfoo.so`` only in ``libone.whl``, you could do::

    auditwheel repair dist/libone.whl
    auditwheel repair dist/libtwo.whl --exclude libfoo.so

In such case you would end up with the following wheels::

    venv/lib/python3.10/site-packages/libone
    ├── __init__.py
    ├── _libone.cpython-310-aarch64-linux-gnu.so
    venv/lib/python3.10/site-packages/libone.libs
    └── libfoo-ef63151d.so
    venv/lib/python3.10/site-packages/libtwo
    ├── __init__.py
    ├── _libtwo.cpython-310-aarch64-linux-gnu.so

The problem would be that while ``_libone.cpython-310-aarch64-linux-gnu.so``
was patched by ``auditwheel`` to know about the ``libfoo-ef63151d.so`` name,
``_libtwo.cpython-310-aarch64-linux-gnu.so`` was not, and so still refers to the
original name::

    $ ldd venv/lib/python3.10/site-packages/libone/_libone.cpython-310-aarch64-linux-gnu.so
	libfoo-ef63151d.so => ../libone.libs/libfoo-ef63151d.so (0x0000ffff8f8f0000)

    $ ldd venv/lib/python3.10/site-packages/libtwo/_libtwo.cpython-310-aarch64-linux-gnu.so
	libfoo.so => not found

Which means that trying to import ``libtwo`` will fail with::

    ImportError: libfoo.so: cannot open shared object file: No such file or directory

Which makes sense, because we actually provided ``libfoo-ef63151d.so`` and not ``libfoo.so``.

To solve this problem ``consolidatewheels`` will patch all provided wheels to make sure that they
share a single naming convention for libraries that were mangled.

After ``consolidatewheels`` is used, the final result would be::

    $ ldd venv/lib/python3.10/site-packages/libone/_libone.cpython-310-aarch64-linux-gnu.so
	libfoo-ef63151d.so => ../libone.libs/libfoo-ef63151d.so (0x0000ffff8f8f0000)

    $ ldd venv/lib/python3.10/site-packages/libtwo/_libtwo.cpython-310-aarch64-linux-gnu.so
	libfoo-ef63151d.so => not found

which would work correctly as far as ``libone`` is imported _before_ ``libtwo`` as they will
both look for ``libfoo-ef63151d.so`` which was loaded already by ``libone``.

OSX Support
~~~~~~~~~~~

``consolidatewheels`` works also in conjunction with ``delocate``, consolidating all libraries
embedded by ``delocate`` and removing duplicates of the embedded libraries when they are provided
in multiple wheels.

Install
-------

Install with::

    $ pip install consolidatewheels

Note that ``consolidatewheels`` requires ``patchelf`` to be available in the system,
and it only works on ``Linux`` systems. But those are the same requirements that
``auditwheel`` has, so you are probably already satisfying them if you use ``auditwheel``.

Usage
-----

Usage instructions::

    consolidatewheels --help

Example::

    consolidatewheels libone.whl libtwo.whl --dest=./consolidated_wheels

For a more complex example and a testing environment, you can take
a look at https://github.com/amol-/wheeldeps which uses ``consolidatewheels``
