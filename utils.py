import json
from configparser import ConfigParser
from operator import attrgetter
from pathlib import Path
from types import SimpleNamespace


def _verify_lockfile():
    """Assert that all the packages in Pipfile are in Pipfile.lock"""

    config = ConfigParser()
    config.read('Pipfile')

    pipfile_packages = set(p.lower().replace('_', '-') for p, _ in
                           config.items('packages') + (
                               config.items('dev-packages') if config.has_section('dev-packages') else []))

    lockfile_data = json.loads(Path('Pipfile.lock').read_text())
    lockfile_packages = set(tuple(lockfile_data['default'].keys()) + tuple(lockfile_data['develop'].keys()))

    assert pipfile_packages.issubset(
        lockfile_packages), '{} package(s) in Pipfile not in Pipfile.lock - pipenv lock'. \
        format(pipfile_packages.difference(lockfile_packages))


def get_packages_from_lockfile():
    """
    Return object that contains default and development packages from Pipfile.lock

    Returns: SimpleNamespace(default=[...], development=[...])

    """

    result = SimpleNamespace(default=list(), development=list())
    lockfile = Path('Pipfile.lock')
    lockfile_data = json.loads(lockfile.read_text())
    for key in ('default', 'develop'):
        for package, version_info in lockfile_data[key].items():
            packages = attrgetter('development' if key == 'develop' else key)(result)
            packages.append(package + version_info['version'])
    return result
