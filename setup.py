from operator import itemgetter
from setuptools import setup, find_packages
from os import path, listdir, walk
from functools import partial, groupby
from ast import parse
from distutils.sysconfig import get_python_lib

if __name__ == "__main__":
    package_name = "offregister_openedx"

    with open(path.join(package_name, "__init__.py")) as f:
        __author__, __version__ = list(
            map(
                lambda buf: next([e.value.s for e in parse(buf).body]),
                list(
                    filter(
                        lambda line: line.startswith("__version__")
                        or line.startswith("__author__"),
                        f,
                    )
                ),
            )
        )

    to_funcs = lambda *paths: (
        partial(path.join, path.dirname(__file__), package_name, *paths),
        partial(path.join, get_python_lib(prefix=""), package_name, *paths),
    )

    _data_join, _data_install_dir = to_funcs("_data")
    conf_join, conf_install_dir = to_funcs("conf")
    config_join, config_install_dir = to_funcs("config")

    setup(
        name=package_name,
        author=__author__,
        version=__version__,
        description="Open EdX deployment module for Fabric (offregister)",
        classifiers=[
            "Development Status :: 7 - Inactive",
            "Intended Audience :: Developers",
            "Topic :: Software Development",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "License :: OSI Approved :: MIT License",
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.7",
        ],
        test_suite=package_name + ".tests",
        packages=find_packages(),
        package_dir={package_name: package_name},
        install_requires=["fab-classic", "paramiko"],
        data_files=[
            (_data_install_dir(), list(map(_data_join, listdir(_data_join())))),
            (conf_install_dir(), list(map(conf_join, listdir(conf_join())))),
        ]
        + [
            (to_dir, list(map(itemgetter(1), this_dir)))
            for to_dir, this_dir in groupby(
                (
                    (
                        config_install_dir(path.relpath(root, config_join())),
                        path.join(root, fname),
                    )
                    for root, dirs, files in walk(config_join(), topdown=False)
                    for fname in files
                ),
                itemgetter(0),
            )
        ],
    )
