"""hugo_jupyter v0.1.1

Use Jupyter notebooks to publish with Hugo.

Usage:
    hugo_jupyter  --init
    hugo_jupyter -h | --help
    hugo_jupyter -V | --version

Options:
    -h --help                 show help and exit
    -V --version              show version and exit
    --init                    Create fabfile and notebooks dir if they do not yet exist

Run ``hugo_jupyter --init`` from the root of your hugo site project to enable support for jupyter notebook rendering.

Then, from the directory root, you can run ``fab ...`` to render, publish, serve notebooks etc.
"""
from pathlib import Path
from subprocess import run
from textwrap import dedent

from docopt import docopt


def main(argv=None):
    args = docopt(__doc__, argv=argv, version='0.1.1')
    assert 'config.toml' in (p.name for p in Path().iterdir()), "config.toml not found in directory. Are you sure you're in the project's root?"
    if args['--init']:
        notebooks_dir = Path('./notebooks/')
        notebooks_dir.mkdir(exist_ok=True)

        with open(Path(Path(__file__).parent, '__fabfile.py')) as fp:
            fabfile = Path('fabfile.py')
            fabfile.write_text(fp.read())

    print(dedent("""
    Successfully initialized. From this directory, the following commands are available.
    Just remember to prepend them with `fab`
    """))

    run(('fab', '-l'))

if __name__ == "__main__":
    main()
