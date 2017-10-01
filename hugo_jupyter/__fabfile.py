import re
import json
import sys
import shlex
import subprocess as sp
from pathlib import Path
from datetime import datetime
from typing import *

import nbformat

from nbconvert import MarkdownExporter
from nbconvert.preprocessors import Preprocessor

from traitlets.config import Config

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

import crayons


from fabric.api import *


@task
def render_notebooks():
    """
    Render jupyter notebooks it notebooks directory to respective markdown in content/post directory.
    """
    notebooks = Path('notebooks').glob('*.ipynb')
    for notebook in notebooks:
        write_hugo_formatted_nb_to_md(notebook)


@task
def serve(hugo_args='', init_jupyter=True):
    """
    Watch for changes in jupyter notebooks and render them anew while hugo runs.

    Args:
        init_jupyter: initialize jupyter if set to True
        hugo_args: command-line arguments to be passed to `hugo server`
    """
    observer = Observer()
    observer.schedule(NotebookHandler(), 'notebooks')
    observer.start()

    hugo_process = sp.Popen(('hugo', 'serve', *shlex.split(hugo_args)))

    if init_jupyter:
        jupyter_process = sp.Popen(('jupyter', 'notebook'), cwd='notebooks')

    local('open http://localhost:1313')

    try:
        print(crayons.green('Successfully initialized server(s)'),
              crayons.yellow('press ctrl+C at any time to quit'),
              )
        while True:
            pass
    except KeyboardInterrupt:
        print(crayons.yellow('Terminating'))
    finally:
        if init_jupyter:
            print(crayons.yellow('shutting down jupyter'))
            jupyter_process.kill()

        print(crayons.yellow('shutting down watchdog'))
        observer.stop()
        observer.join()
        print(crayons.yellow('shutting down hugo'))
        hugo_process.kill()
        print(crayons.green('all processes shut down successfully'))
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


def notebook_to_markdown(path: Union[Path, str]) -> str:
    """
    Convert jupyter notebook to hugo-formatted markdown string

    Args:
        path: path to notebook

    Returns: hugo-formatted markdown

    """
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


def write_hugo_formatted_nb_to_md(notebook: Union[Path, str]):
    """
    Convert Jupyter notebook to markdown and write it to the appropriate file.

    Args:
        notebook: The path to the notebook to be rendered
    """
    notebook = Path(notebook)
    rendered_markdown_string = notebook_to_markdown(notebook)
    slug = json.loads(notebook.read_text())['metadata']['front-matter']['slug']
    rendered_markdown_file = Path('content/post/', slug + '.md')
    rendered_markdown_file.write_text(rendered_markdown_string)
    print(notebook.name, '->', rendered_markdown_file.name)


def update_notebook_front_matter(notebook: Union[Path, str],
                                 title: Union[None, str]=None,
                                 subtitle: Union[None, str]=None,
                                 date: Union[None, str]=None,
                                 slug: Union[None, str]=None):
    """
    Update the notebook's front-matter

    Args:
        notebook: notebook to have edited
    """
    notebook_path: Path = Path(notebook)
    notebook_data: dict = json.loads(notebook_path.read_text())
    old_front_matter: dict = notebook_data.get('metadata', {}).get('front-matter', {})

    # generate front-matter fields
    title = title or old_front_matter.get('title') or notebook_path.stem
    subtitle = subtitle or old_front_matter.get('subtitle') or 'Generic subtitle'
    date = date or old_front_matter.get('date') or datetime.now().strftime('%Y-%m-%d')
    slug = slug or old_front_matter.get('slug') or title.lower().replace(' ', '-')

    front_matter = {
        'title': title,
        'subtitle': subtitle,
        'date': date,
        'slug': slug,
    }

    notebook_data['metadata']['front-matter'] = front_matter

    # write over old notebook with new front-matter
    notebook_path.write_text(json.dumps(notebook_data))





########## Watchdog stuff #################

class NotebookHandler(PatternMatchingEventHandler):
    patterns = ["*.ipynb"]

    def process(self, event):
        try:
            # don't automatically update front matter
            # and render notebook until filename is
            # changed from untitled...
            if 'untitled' not in event.src_path.lower():
                self.delete_notebook_md(event)
                update_notebook_front_matter(event.src_path)
                write_hugo_formatted_nb_to_md(event.src_path)
        except Exception as e:
            print('could not successfully render', event.src_path)
            print(e)

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.delete_notebook_md(event)

    def delete_notebook_md(self, event):
        possible_rendered_markdown_paths = self.get_possible_rendered_md_paths(event)
        for path in possible_rendered_markdown_paths:
            if path.exists():
                path.unlink()
                print(crayons.yellow('removed post: {}'.format(path)))

    def get_possible_rendered_md_paths(self, event):
        source_path = Path(event.src_path)
        slug = json.loads(source_path.read_text())['metadata']['front-matter']['slug']
        return [
            Path('content/post/' + slug + '.md'),
            Path('content/post/' + source_path.stem + '.md'),
            ]

