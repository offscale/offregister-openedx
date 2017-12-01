from operator import itemgetter
from setuptools import setup, find_packages
from os import path, listdir, walk
from functools import partial
from itertools import imap, ifilter, groupby
from ast import parse
from distutils.sysconfig import get_python_lib

if __name__ == '__main__':
    package_name = 'offregister_openedx'

    with open(path.join(package_name, '__init__.py')) as f:
        __author__, __version__ = imap(
            lambda buf: next(imap(lambda e: e.value.s, parse(buf).body)),
            ifilter(lambda line: line.startswith('__version__') or line.startswith('__author__'), f)
        )

    to_funcs = lambda *paths: (partial(path.join, path.dirname(__file__), package_name, *paths),
                               partial(path.join, get_python_lib(prefix=''), package_name, *paths))

    _data_join, _data_install_dir = to_funcs('_data')
    conf_join, conf_install_dir = to_funcs('conf')
    config_join, config_install_dir = to_funcs('config')

    setup(
        name=package_name,
        author=__author__,
        version=__version__,
        test_suite=package_name + '.tests',
        packages=find_packages(),
        package_dir={package_name: package_name},
        install_requires=['fabric'],
        data_files=[(_data_install_dir(), map(_data_join, listdir(_data_join()))),
                    (conf_install_dir(), map(conf_join, listdir(conf_join())))
                    ] + [(to_dir, map(itemgetter(1), this_dir))
                         for to_dir, this_dir in groupby(((config_install_dir(path.relpath(root, config_join())),
                                                           path.join(root, fname))
                                                          for root, dirs, files in walk(config_join(), topdown=False)
                                                          for fname in files), itemgetter(0))]

    )
