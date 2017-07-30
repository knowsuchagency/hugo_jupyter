from functools import partial
from functools import singledispatch
from io import StringIO

from utils import _verify_lockfile, get_packages_from_lockfile

from fabric.tasks import Task
from fabric.api import *

from colorama import init, Back
init(autoreset=True)


def print_in_color(color, *args, **kwargs):
    """Print text in a given color."""
    file = kwargs.pop('file', None)
    with StringIO('w+') as fp:
        fp.write(color)
        print(*args, file=fp, **kwargs)
        fp.seek(0)
        print(fp.read().strip(), file=file)


print_red = partial(print_in_color, Back.RED)
print_green = partial(print_in_color, Back.GREEN)
print_yellow = partial(print_in_color, Back.YELLOW)


@task
def clean_build():
    """Remove build artifacts."""
    local('rm -fr build/')
    local('rm -fr dist/')
    local('rm -rf .eggs/')
    local("find . -name '*.egg-info' -exec rm -fr {} +")
    local("find . -name '*.egg' -exec rm -f {} +")


@task
def clean_pyc():
    """Remove Python file artifacts."""
    local("find . -name '*.pyc' -exec rm -f {} +")
    local("find . -name '*.pyo' -exec rm -f {} +")
    local("find . -name '*~' -exec rm -f {} +")
    local("find . -name '__pycache__' -exec rm -fr {} +")


@task
def clean_test():
    """Remove test and coverage artifacts."""
    local('rm -fr .tox/')
    local('rm -f .coverage')
    local('rm -fr htmlcov/')


@task
def clean():
    """Remove all build, test, coverage and Python artifacts."""
    clean_build()
    clean_pyc()
    clean_test()


@task
def test(capture=True):
    """
    Run tests quickly with default Python.

    Args:
        capture: capture stdout [default: True]
    """
    disable_capturing = ' -s' if not true(capture) else ''
    verify_lockfile.run()
    local('py.test' + disable_capturing)


@task(alias='tox')
def test_all(absolute_path=None):
    """Run on multiple Python versions with tox."""
    from pathlib import Path

    # This happens to be where I have Python 3.5 installed; may well be different for others. Edit as necessary.
    py35_path = Path(Path.home(), '.pyenv/versions/3.5.2/bin') if absolute_path is None else Path(absolute_path)

    with path(str(py35_path.absolute())):
        local('tox')


@task
def coverage(open_browser=True):
    """Check code coverage quickly with the default Python."""
    local('coverage run --source hugo_jupyter -m pytest')
    local('coverage report -m')
    local('coverage html')
    if true(open_browser):
        local('open htmlcov/index.html')


@task
def docs(open_browser=True):
    """
    Generage Sphinx HTML documentation, including API docs.

    Args:
        open_browser: Open browser automatically after building docs
    """
    local('rm -f docs/hugo_jupyter.rst')
    local('rm -f docs/modules.rst')
    local('rm -f docs/hugo_jupyter*')
    local('sphinx-apidoc -o docs/ hugo_jupyter')

    with lcd('docs'):
        local('make clean')
        local('make html')

    local('cp -rf docs/_build/html/ public/')

    if true(open_browser):
        local('open public/index.html')


@task
def publish_docs():
    """
    Compile docs and publish to GitHub Pages.

    Logic borrowed from `hugo <https://gohugo.io/tutorials/github-pages-blog/>`
    """
    from textwrap import dedent

    with settings(warn_only=True):
        if local('git diff-index --quiet HEAD --').failed:
            local('git status')
            abort('The working directory is dirty. Please commit any pending changes.')

        if local('git show-ref refs/heads/gh-pages').failed:
            # initialized github pages branch
            local(dedent("""
                git checkout --orphan gh-pages
                git reset --hard
                git commit --allow-empty -m "Initializing gh-pages branch"
                git push gh-pages
                git checkout master
                """).strip())
            print_green('created github pages branch')

    # deleting old publication
    local('rm -rf public')
    local('mkdir public')
    local('git worktree prune')
    local('rm -rf .git/worktrees/public/')
    # checkout out gh-pages branch into public
    local('git worktree add -B gh-pages public gh-pages')
    # generating docs
    docs(open_browser=False)
    # push to github
    with lcd('public'), settings(warn_only=True):
        local('git add .')
        local('git commit -m "Publishing to gh-pages (Fabfile)"')
        local('git push origin gh-pages')


@task
def dist():
    """Build source and wheel package."""
    clean()
    local('python setup.py sdist')
    local('python setup.py bdist_wheel')


@task
def release():
    """Package and upload a release to pypi."""
    clean()
    test_all()
    publish_docs()
    local('python setup.py sdist upload')
    local('python setup.py bdist_wheel upload')


@task
def gen_requirements_txt(with_dev=True):
    """
    Generate a requirements.txt from Pipfile.lock

    This is more for the benefit of third-party packages
    like pyup.io that need requirements.txt
    """
    from pathlib import Path

    verify_lockfile.run()

    packages = get_packages_from_lockfile()

    requirements_file = Path('requirements.txt')

    requirements_file.write_text('\n'.join(packages.default + (packages.development if true(with_dev) else [])))
    print_green('successfully generated requirements.txt')


class VerifyLockfile(Task):
    name = 'verify_lockfile'

    def set_docstring(func):
        func.__doc__ = _verify_lockfile.__doc__
        return func

    @set_docstring
    def run(self):
        _verify_lockfile()
        print_green('lockfile verified')


verify_lockfile = VerifyLockfile()
verify_lockfile.__doc__ = _verify_lockfile.__doc__


@singledispatch
def true(arg):
    """
    Determine of the argument is True.

    Since arguments coming from the command line
    will always be interpreted as strings by fabric
    this helper function just helps us to do what is
    expected when arguments are passed to functions
    explicitly in code vs from user input.

    Just make sure NOT to do the following with task arguments:

    @task
    def foo(arg):
        if arg: ...

    Always wrap the conditional as so

    @task
    def foo(arg):
        if true(arg): ...

    and be aware that true('false') -> False

    Args:
        arg: anything

    Returns: bool

    """
    return bool(arg)


@true.register(str)
def _(arg):
    """If the lowercase string is 't' or 'true', return True else False."""
    argument = arg.lower().strip()
    return argument == 'true' or argument == 't'
