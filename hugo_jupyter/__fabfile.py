import json
import re
import shlex
import shutil
import subprocess as sp
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import *
import time

import crayons
import nbformat
from fabric.api import *
from nbconvert import MarkdownExporter
from nbconvert.preprocessors import Preprocessor
from nbconvert.writers import FilesWriter
from traitlets.config import Config
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


@task
def update_notebooks_metadata():
    """Updates all the notebooks' metadata fields."""
    # noinspection SpellCheckingInspection
    notebooks = Path('notebooks').glob('*.ipynb')
    for notebook in notebooks:
        if str(notebook).startswith('.'):
            pass
        elif 'untitled' in str(notebook).lower():
            pass
        else:
            update_notebook_metadata(notebook)


@task
def render_notebooks():
    """Renders jupyter notebooks it notebooks directory to respective markdown
    in content/post directory.
    """
    notebooks = Path('notebooks').glob('*.ipynb')
    for notebook in notebooks:
        write_hugo_formatted_nb_to_md(notebook)


@task
def serve(hugo_args='', init_jupyter=True):
    """Watches for changes in jupyter notebooks and render them anew while hugo
    runs.

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

    webbrowser.open('http://localhost:1313')

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
            print(crayons.yellow('Info - Shutting down jupyter'))
            jupyter_process.kill()

        print(crayons.yellow('Info - Shutting down watchdog'))
        observer.stop()
        observer.join()
        print(crayons.yellow('Info - Shutting down hugo'))
        hugo_process.kill()
        print(crayons.green('Info - All processes shut down successfully'))
        sys.exit(0)


@task
def publish():
    """
    Publishes notebook to github pages.

    Assumes this is yourusername.github.io repo aka
    User Pages site as described in
    https://help.github.com/articles/user-organization-and-project-pages/
    and that you're using the master branch only
    to have the rendered content of your blog.
    """
    with settings(warn_only=True):
        if local('git diff-index --quiet HEAD --').failed:
            local('git status')
            abort('The working directory is dirty. Please commit any pending'
                  'changes.')

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


# Jupyter stuff

class CustomPreprocessor(Preprocessor):
    """Removes blank code cells and unnecessary whitespace."""

    def preprocess(self, nb, resources):
        """Remove blank cells
        """
        for index, cell in enumerate(nb.cells):
            if cell.cell_type == 'code' and not cell.source:
                nb.cells.pop(index)
            else:
                nb.cells[index], resources = self.preprocess_cell(
                    cell, resources, index)
        return nb, resources

    def preprocess_cell(self, cell, resources, cell_index):
        """Removes extraneous whitespace from code cells' source code
        """
        if cell.cell_type == 'code':
            cell.source = cell.source.strip()

        return cell, resources


def doctor(string: str) -> str:
    """Gets rid of all the wacky newlines nbconvert adds to markdown output and
    return result."""
    post_code_newlines_patt = re.compile(r'(```)(\n+)')
    inter_output_newlines_patt = re.compile(r'(\s{4}\S+)(\n+)(\s{4})')

    post_code_filtered = re.sub(post_code_newlines_patt, r'\1\n\n', string)
    inter_output_filtered = re.sub(
        inter_output_newlines_patt, r'\1\n\3', post_code_filtered)

    return inter_output_filtered


def notebook_to_markdown(notebook_path: Union[Path, str]) -> Tuple[str, dict]:
    """Converts jupyter notebook to hugo-formatted markdown string and returns
    the markdown string along with the resources (e.g. images).

    Args:
        notebook_path: path to notebook

    Returns:
        output: markdown string
        resources: dictionary containing additional notebook resources

    """
    with open(notebook_path) as fp:
        notebook = nbformat.read(fp, as_version=4)
        front_matter_dict = dict(notebook['metadata']['front-matter'])
        front_matter = json.dumps(front_matter_dict, indent=2)

    c = Config()
    c.MarkdownExporter.preprocessors = [CustomPreprocessor]
    markdown_exporter = MarkdownExporter(config=c)

    markdown, resources = markdown_exporter.from_notebook_node(notebook)
    markdown = doctor(markdown)

    # added <!--more--> comment to prevent summary creation
    markdown = '\n'.join(
        ['---', front_matter, '---', '<!--more-->', markdown])

    return markdown, resources


def write_hugo_formatted_nb_to_md(
        notebook_path: Path,
        render_to: Optional[Union[Path, str]] = None):
    """Converts Jupyter notebook to markdown and writes the markdown file to the
    ``content/`` and resources to ``static/resources``.

    Note that, when the markdown file is placed in ``content/post/<name>.md``,
    resources are located in ``static/resources/post/<name>/.

    Args:
        notebook_path: The path to the notebook to be rendered
        render_to: The directory we want to render the notebook to
    """
    notebook_metadata = json.loads(notebook_path.read_text())['metadata']
    rendered_md_string, rendered_md_resources = notebook_to_markdown(
        notebook_path)
    slug = notebook_metadata['front-matter']['slug']
    render_to = (render_to or notebook_metadata['hugo-jupyter']['render-to'] or
                 'content/post/')

    if not render_to.endswith('/'):
        render_to += '/'

    rendered_md_path = Path(render_to, slug + '.md')
    rendered_md_resources_path = Path(
        f'static/resources/{rendered_md_path.parent.stem}/{slug}')

    if not rendered_md_path.parent.exists():
        rendered_md_path.parent.mkdir(parents=True)
    if not rendered_md_resources_path.exists():
        rendered_md_resources_path.mkdir(parents=True)

    # Adjust image paths to static
    rendered_md_string = rendered_md_string.replace(
        '![png](output_', f'![png](/resources/blog/{slug}/output_')

    # Write markdown to render_to
    c = Config()
    c.FilesWriter.build_directory = str(rendered_md_path.parent)
    fw = FilesWriter(config=c)
    fw.write(output=rendered_md_string, resources={'output_extension': '.md'},
             notebook_name=rendered_md_path.stem)
    # Write resources to static if exist
    if rendered_md_resources['outputs']:
        c.FilesWriter.build_directory = str(rendered_md_resources_path)
        fw = FilesWriter(config=c)
        fw.write(output='', resources=rendered_md_resources,
                 notebook_name=rendered_md_path.stem)
        # Remove empty markdown created by writing resources
        Path(rendered_md_resources_path, rendered_md_path.name).unlink()

    # Print status message
    print(notebook_path.name, '->', rendered_md_path.name)


def update_notebook_metadata(notebook_path: Path,
                             title: Union[None, str] = None,
                             subtitle: Union[None, str] = None,
                             date: Union[None, str] = None,
                             slug: Union[None, str] = None,
                             toc: Union[None, str] = None,
                             render_to: str = None):
    """Updates the notebook's metadata for hugo rendering.

    Args:
        title: title of the post
        subtitle: subtitle of the post
        date: date of the post
        slug: short name of the post with hyphens instead of whitespaces
        notebook: path to notebook which needs metadata update
        toc: identifier whether table of content should be displayed
        render_to: destination path for rendered notebook
    """
    notebook_data: dict = json.loads(notebook_path.read_text())
    old_front_matter: dict = notebook_data.get(
        'metadata', {}).get('front-matter', {})

    # generate front-matter fields
    title = title or old_front_matter.get('title') or notebook_path.stem
    subtitle = (subtitle or old_front_matter.get('subtitle') or
                'Generic subtitle')
    date = (date or old_front_matter.get('date') or
            datetime.now().strftime('%Y-%m-%d'))
    slug = (slug or old_front_matter.get('slug') or
            title.lower().replace(' ', '-'))
    toc = toc or old_front_matter.get('toc') or 'true'

    front_matter = {
        'title': title,
        'subtitle': subtitle,
        'date': date,
        'slug': slug,
        'toc': toc,
    }

    # update front-matter
    notebook_data['metadata']['front-matter'] = front_matter

    # update hugo-jupyter settings
    render_to = render_to or notebook_data['metadata'].get(
        'hugo-jupyter', {}).get('render-to') or 'content/post/'

    hugo_jupyter = {
        'render-to': render_to
    }

    notebook_data['metadata']['hugo-jupyter'] = hugo_jupyter

    # write over old notebook with new front-matter
    notebook_path.write_text(json.dumps(notebook_data))

    # make the notebook trusted again, now that we've changed it
    sp.run(['jupyter', 'trust', str(notebook_path)])

    print(f'Info - Changed notebook metadata for {notebook}')


def update_notebook_name(notebook_path: Union[Path, str], slug):
    """Renames the notebook so that it matches the slug of the article."""
    new_notebook_path = Path(notebook).with_name(slug + '.ipynb')
    # Rename file
    notebook_path.replace(new_notebook_path)

    print(f'Renamed {notebook_path} to {new_notebook_path}')


# Watchdog stuff

class NotebookHandler(PatternMatchingEventHandler):
    """Handles the processing of notebooks to Hugo posts based on file
    events.

    Attributes:
        patterns (list): files to include
        ignore_patterns (list): files to exclude
    """
    patterns = ['*.ipynb']
    ignore_patterns = ['*.~*.ipynb', '*Untitled*.ipynb', ]

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

    def process(self, event):
        try:
            # If ``event.src_path`` and ``event.dest_path`` match, the notebook
            # was not renamed. Use ``event.dest_path`` if the file was renamed.
            try:
                notebook_path = Path(event.dest_path)
            except AttributeError:
                notebook_path = Path(event.src_path)
            # This if-else block captures modified notebooks which do not
            # have updated metadata. If a notebook does not have the updated
            # metadata, the metadata is updated and since the notebook is
            # altered ``def on_modified`` is called subsequently.
            if not self.get_render_to_field(notebook_path):
                print(f'Info - Modified {notebook_path} has no render-to '
                      f'field.')
                update_notebook_metadata(notebook_path)
            elif self.get_slug_field(notebook_path) != notebook_path.stem:
                print(f'Info - Modified {notebook_path} is not correctly '
                      f'named.')
                update_notebook_name(notebook_path,
                                     self.get_slug_field(notebook_path))
            else:
                print(f'Info - Notebook {notebook_path} has render-to field.')

                render_to = self.get_render_to_field(notebook_path)
                self.delete_notebook_md(notebook_path)

                write_hugo_formatted_nb_to_md(
                    notebook_path, render_to=render_to)

        except Exception as e:
            print(f'Error - Could not render {event.src_path} successfully.')
            raise e

    def on_modified(self, event):
        """If a file is modified, process the notebook."""
        print('Event - Modified - Sleeps 5 sec.')
        time.sleep(5)
        self.process(event)

    def on_created(self, event):
        """If a file is created, update the notebook metadata. Since this
        process alters the notebook, ``def on_modified`` is called
        automatically afterwards."""
        print('Event - Created')
        update_notebook_metadata(event.src_path)

    def on_deleted(self, event):
        print('Event - Deleted')
        self.delete_notebook_md(event)

    @staticmethod
    def delete_notebook_md(notebook_path: Path):
        print(f"Info - Attempting to delete the post for {notebook_path}")
        # There are two possible ways to call the function. First, the function
        # is called via ``def process`` and the ``render_to`` field exists.
        # Then, there are two cases where ``render_to`` was changed which
        # caused the event and where it did not change. Second, this function
        # is called via ``def on_deleted``. In the second case, it is clear
        # that the information on ``render_to`` is gone with the notebook and
        # we have to look in each folder. In all of the cases we cannot be sure
        # where the notebook was previously located. Therefore, loop through
        # the directories and do not name notebooks and articles the same!
        for render_to in ['content/blog/', 'content/post/']:
            content_type = Path(render_to).stem
            markdown_path = Path(render_to, str(notebook_path.stem) + '.md')
            print(str(markdown_path))
            if markdown_path.exists():
                # Remove post
                markdown_path.unlink()
                # Remove resources
                path_resources = Path('static', 'resources', content_type,
                                      markdown_path.stem)
                shutil.rmtree(str(path_resources))
                print(f'Info - Removed post and resources: {str(path)}, '
                      f'{path_resources}')
            else:
                print('Info - Post does not exist')

    @staticmethod
    def get_render_to_field(notebook_path: Path) -> str:
        """Tries to get the ``render-to`` field from the notebook and returns
        and empty string if it does not exist."""
        try:
            render_to = json.loads(
                notebook_path.read_text())[
                    'metadata']['hugo-jupyter']['render-to']
            return render_to
        except json.JSONDecodeError as e:
            print(crayons.yellow(
                f"could not marshal notebook to json: {notebook_path}"))
            raise e
        except KeyError:
            print(f"{notebook_path} has no field hugo-jupyter.render-to in"
                  "its metadata")
            return ''

    @staticmethod
    def get_slug_field(notebook_path: Path) -> str:
        """Tries to get the ``render-to`` field from the notebook and returns
        and empty string if it does not exist."""
        try:
            slug = json.loads(
                notebook_path.read_text())[
                    'metadata']['front-matter']['slug']
            return slug
        except json.JSONDecodeError as e:
            print(crayons.yellow(
                f"could not marshal notebook to json: {notebook_path}"))
            raise e
        except KeyError:
            print(f"{notebook_path} has no field hugo-jupyter.render-to in"
                  "its metadata")
            return ''
