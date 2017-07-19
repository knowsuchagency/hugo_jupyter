import re
import json
import sys
import subprocess as sp
from pathlib import Path
from typing import *

import nbformat

from nbconvert import MarkdownExporter
from nbconvert.preprocessors import Preprocessor

from traitlets.config import Config

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from colorama import Fore, init

init()

from fabric.api import *


@task
def render_notebooks():
    """
    Render jupyter notebooks it notebooks directory to respective markdown in content/post directory.
    """
    notebooks = Path('notebooks').glob('*.ipynb')
    for notebook in notebooks:
        write_jupyter_to_md(notebook)


@task
def serve(init_jupyter=True):
    """
    Watch for changes in jupyter notebooks and render them anew while hugo runs.

    Args:
        init_jupyter: initialize jupyter if set to True
    """
    observer = Observer()
    observer.schedule(NotebookHandler(), 'notebooks')
    observer.start()

    hugo_process = sp.Popen(('hugo', 'serve'))

    if init_jupyter:
        jupyter_process = sp.Popen(('jupyter', 'notebook'), cwd='notebooks')

    local('open http://localhost:1313')

    try:
        print(Fore.GREEN + 'Successfully initialized server(s)',
              Fore.YELLOW + 'press ctrl+C at any time to quit',
              Fore.WHITE)
        while True:
            pass
    except KeyboardInterrupt:
        print(Fore.YELLOW + 'Terminating')
    finally:
        if init_jupyter:
            print(Fore.YELLOW + 'shutting down jupyter')
            jupyter_process.kill()

        print(Fore.YELLOW + 'shutting down watchdog')
        observer.stop()
        observer.join()
        print(Fore.YELLOW + 'shutting down hugo')
        hugo_process.kill()
        print(Fore.GREEN + 'all processes shut down successfully')
        sys.exit(0)


@task
def publish():
    """
    Publish notebook to github pages.

    Assumes this is yourusername.github.io repo aka
    User Pages site as described in
    https://help.github.com/articles/user-organization-and-project-pages/
    and that you're using the master branch only
    to have the rendered content of your blog.
    """
    with settings(warn_only=True):
        if local('git diff-index --quiet HEAD --').failed:
            local('git status')
            abort('The working directory is dirty. Please commit any pending changes.')

    # deleting old publication
    local('rm -rf public')
    local('mkdir public')
    local('git worktree prune')
    local('rm -rf .git/worktrees/public/')

    # checkout out gh-pages branch into public
    local('git worktree add -B master public upstream/master')

    # removing any existing files
    local('rm -rf public/*')

    # generating site
    render_notebooks()
    local('hugo')

    # commit
    with lcd('public'), settings(warn_only=True):
        local('git add .')
        local('git commit -m "Committing to master (Fabfile)"')

    # push to master
    local('git push upstream master')
    print('push succeeded')


########## Jupyter stuff #################

class CustomPreprocessor(Preprocessor):
    """Remove blank code cells and unnecessary whitespace."""

    def preprocess(self, nb, resources):
        """
        Remove blank cells
        """
        for index, cell in enumerate(nb.cells):
            if cell.cell_type == 'code' and not cell.source:
                nb.cells.pop(index)
            else:
                nb.cells[index], resources = self.preprocess_cell(cell, resources, index)
        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        """
        Remove extraneous whitespace from code cells' source code
        """
        if cell.cell_type == 'code':
            cell.source = cell.source.strip()

        return cell, resources


def doctor(string: str) -> str:
    """Get rid of all the wacky newlines nbconvert adds to markdown output and return result."""
    post_code_newlines_patt = re.compile(r'(```)(\n+)')
    inter_output_newlines_patt = re.compile(r'(\s{4}\S+)(\n+)(\s{4})')

    post_code_filtered = re.sub(post_code_newlines_patt, r'\1\n\n', string)
    inter_output_filtered = re.sub(inter_output_newlines_patt, r'\1\n\3', post_code_filtered)

    return inter_output_filtered


def convert_notebook_to_hugo_markdown(path: Union[Path, str]) -> str:
    with open(Path(path)) as fp:
        notebook = nbformat.read(fp, as_version=4)
        assert 'front-matter' in notebook['metadata'], "You must have a front-matter field in the notebook's metadata"
        front_matter_dict = dict(notebook['metadata']['front-matter'])
        front_matter = json.dumps(front_matter_dict, indent=2)

    c = Config()
    c.MarkdownExporter.preprocessors = [CustomPreprocessor]
    markdown_exporter = MarkdownExporter(config=c)

    markdown, _ = markdown_exporter.from_notebook_node(notebook)
    doctored_md = doctor(markdown)
    # added <!--more--> comment to prevent summary creation
    output = '\n'.join(('---', front_matter, '---', '<!--more-->', doctored_md))

    return output


def write_jupyter_to_md(notebook):
    notebook = Path(notebook)
    hugo_markdown = convert_notebook_to_hugo_markdown(notebook)
    front_matter = json.loads(notebook.read_text())['metadata']['front-matter']
    if 'slug' in front_matter:
        slug = front_matter['slug']
    else:
        slug = '-'.join(e for e in front_matter['title'].lower().split())
    hugo_file = Path('content/post/', slug + '.md')
    hugo_file.write_text(hugo_markdown)
    print(notebook.name, '->', hugo_file.name)


########## Watchdog stuff #################

class NotebookHandler(PatternMatchingEventHandler):
    patterns = ["*.ipynb"]

    def process(self, event):
        try:
            write_jupyter_to_md(event.src_path)
        except Exception as e:
            print('could not successfully render', event.src_path)
            print(e)

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)
