============
Hugo Jupyter
============


.. image:: https://img.shields.io/pypi/v/hugo_jupyter.svg
        :target: https://pypi.python.org/pypi/hugo_jupyter

.. image:: https://img.shields.io/travis/knowsuchagency/hugo_jupyter.svg
        :target: https://travis-ci.org/knowsuchagency/hugo_jupyter

.. image:: https://pyup.io/repos/github/knowsuchagency/hugo_jupyter/shield.svg
     :target: https://pyup.io/repos/github/knowsuchagency/hugo_jupyter/
     :alt: Updates

.. image:: https://img.shields.io/github/license/mashape/apistatus.svg



Use Jupyter notebooks to publish with Hugo.


* Documentation: https://knowsuchagency.github.io/hugo_jupyter
* Source: https://github.com/knowsuchagency/hugo_jupyter


Installation
------------

.. code-block:: bash

    pip install hugo_jupyter

Usage
-----

From your hugo project's root

.. code-block:: bash

    hugo_jupyter --init

This will create a ``notebooks`` directory at the root of your hugo project if it doesn't yet exist.
Any jupyter notebooks you want rendered should go in this directory.

Then, from the root of your hugo project, you can type ``fab serve`` to automatically initialize
your jupyter server, hugo server, and watchdog to re-render your jupyter notebooks to markdown for hugo
as you create and edit them.
