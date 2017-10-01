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



Publish Jupyter_ notebooks with Hugo_.


* Documentation: https://knowsuchagency.github.io/hugo_jupyter
* Source: https://github.com/knowsuchagency/hugo_jupyter


Installation
------------

.. code-block:: bash

    pip install hugo_jupyter

Usage
-----

.. image:: example_movie.gif
    :target: https://youtu.be/LtdyM4hP85I

.. code-block:: bash

    cd root_of_hugo_project
    hugo_jupyter --init

This will create a ``notebooks`` directory at the root of your hugo project if it doesn't yet exist.
Any jupyter notebooks you want rendered should go in the ``notebooks`` directory.

In addition, a fabfile.py script will be written at the project root.

.. code-block:: bash

    fab serve

Automatically initializes your jupyter server, hugo server, and watchdog to re-render
your jupyter notebooks to markdown for hugo as you create and edit them.


Jupyter Notebooks
-----------------

Any notebooks that you create will need `front matter`_ for hugo to know how to render the content.

Once you edit the name of the jupyter notebook to something other than ``Untitled*.ipynb``, hugo-jupyter will
automatically edit the notebook's metadata to enable rendering with jupyter. You may need to reload the
notebook page to see the changes in the metadata.

There will also be a ``hugo-jupyter`` dictionary in the notebook's metadata with a ``render-to`` field
automatically set to ``content/post/``. You can edit this field to edit where the notebook's markdown
will be rendered to.

.. image:: http://i.imgur.com/ynQs0gB.png

.. image:: http://i.imgur.com/Jcjwc0y.png

.. _front matter: https://gohugo.io/content-management/front-matter/
.. _hugo: https://gohugo.io/
.. _jupyter: http://jupyter.org/
