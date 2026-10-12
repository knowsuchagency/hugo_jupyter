#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `hugo_jupyter` package."""

import base64
import importlib
import json
from pathlib import Path

import nbformat
import pytest
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent

from hugo_jupyter import cli

fabfile = importlib.import_module('hugo_jupyter.__fabfile')

# a 1x1 transparent png
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A minimal hugo site with a notebooks directory, as the cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'config.toml').write_text('')
    (tmp_path / 'notebooks').mkdir()
    return tmp_path


def write_notebook(path, front_matter=None):
    nb = new_notebook()
    nb.cells = [
        new_markdown_cell('Some *text*.'),
        new_code_cell(''),
        new_code_cell(''),
        new_code_cell('plot()', outputs=[new_output(
            'display_data', data={'image/png': base64.b64encode(PNG).decode()})]),
    ]
    if front_matter is not None:
        nb.metadata['front-matter'] = front_matter
    nbformat.write(nb, str(path))
    return path


def test_render_keeps_custom_front_matter_and_writes_images(site):
    notebook = write_notebook(site / 'notebooks' / 'my-post.ipynb', front_matter={
        'title': 'My Post', 'slug': 'my-post', 'author': 'Ada', 'tags': ['a', 'b']})

    rendered = fabfile.write_hugo_formatted_nb_to_md(notebook)

    assert rendered == Path('content/post/my-post.md')
    markdown = rendered.read_text()
    front_matter = json.loads(markdown.split('---\n')[1])
    assert front_matter['author'] == 'Ada'
    assert front_matter['tags'] == ['a', 'b']
    assert front_matter['subtitle'] == 'Generic subtitle'

    assert '](/notebooks/my-post/output_' in markdown
    images = list((site / 'static' / 'notebooks' / 'my-post').iterdir())
    assert len(images) == 1
    assert images[0].read_bytes() == PNG
    assert '](/notebooks/my-post/{})'.format(images[0].name) in markdown

    # the metadata also survives in the notebook itself
    metadata = json.loads(notebook.read_text())['metadata']
    assert metadata['front-matter']['author'] == 'Ada'


def test_render_new_notebook_without_front_matter(site):
    notebook = write_notebook(site / 'notebooks' / 'Hello World.ipynb')

    rendered = fabfile.write_hugo_formatted_nb_to_md(notebook)

    assert rendered == Path('content/post/hello-world.md')


def test_blank_code_cells_are_dropped(site):
    notebook = write_notebook(site / 'notebooks' / 'blank.ipynb')
    markdown, _ = fabfile.notebook_to_markdown(notebook)
    assert markdown.count('```') == 2  # only the plot() cell


def test_metadata_update_is_idempotent(site):
    notebook = write_notebook(site / 'notebooks' / 'post.ipynb')
    fabfile.update_notebook_metadata(notebook)
    first = notebook.read_text()
    mtime = notebook.stat().st_mtime_ns

    fabfile.update_notebook_metadata(notebook)

    # no rewrite, so watchdog sees no new modified event
    assert notebook.read_text() == first
    assert notebook.stat().st_mtime_ns == mtime


@pytest.mark.parametrize('name, ignored', [
    ('notebooks/.~hello.ipynb', True),
    ('notebooks/Untitled1.ipynb', True),
    ('notebooks/.ipynb_checkpoints/post-checkpoint.ipynb', True),
    ('notebooks/post.ipynb', False),
])
def test_is_ignored_notebook(name, ignored):
    assert fabfile.is_ignored_notebook(name) is ignored


def test_handler_ignores_vanished_temp_file(site, capsys):
    handler = fabfile.NotebookHandler()
    # jupyter's temporary copy, already deleted by the time we see the event
    handler.on_created(FileCreatedEvent('notebooks/.~hello.ipynb'))
    handler.on_modified(FileModifiedEvent('notebooks/.~hello.ipynb'))
    assert 'could not' not in capsys.readouterr().out
    assert not (site / 'content').exists()


def test_handler_renders_on_create_modify_and_rename(site):
    handler = fabfile.NotebookHandler()
    untitled = write_notebook(site / 'notebooks' / 'Untitled.ipynb')
    handler.on_created(FileCreatedEvent(str(untitled)))
    assert not (site / 'content').exists()

    renamed = site / 'notebooks' / 'first.ipynb'
    untitled.rename(renamed)
    handler.on_moved(FileMovedEvent(str(untitled), str(renamed)))
    post = site / 'content' / 'post' / 'first.md'
    assert post.exists()

    # a missing notebook is reported, not raised
    handler.on_modified(FileModifiedEvent('notebooks/gone.ipynb'))

    handler.on_deleted(type('E', (), {'src_path': str(renamed)})())
    assert not post.exists()


def test_cli_init_writes_fabfile(site, monkeypatch):
    monkeypatch.setattr(cli, 'run', lambda *a, **k: None)
    cli.main(['--init'])
    assert Path('fabfile.py').read_text() == Path(fabfile.__file__).read_text()


def test_cli_accepts_hugo_toml(site, monkeypatch):
    monkeypatch.setattr(cli, 'run', lambda *a, **k: None)
    (site / 'config.toml').rename(site / 'hugo.toml')
    cli.main(['--init'])
    assert Path('fabfile.py').exists()


def test_cli_requires_hugo_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(AssertionError):
        cli.main(['--init'])
