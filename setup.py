import os

from setuptools import find_packages, setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="Odoo Analyse",
    version="0.1",
    author="initOS GmbH",
    author_email="info@initos.com",
    description="Package to analyse and visualize odoo modules",
    long_description=read('README.md'),
    license="AGPL-3.0",
    keywords="odoo, modules, analyze, dependency, graph",
    url="https://github.com/initOS/odoo-analyse",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={
        'console_scripts':
            ['odoo_analyse = odoo_analyse.main:main'],
    },
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*",
    install_requires=[
        "2to3",
        "cloc",
        "lxml",
    ],
    extras_require={
        "console": [
            "graphviz",
        ],
    },
    project_urls={
        'Documentation': 'https://github.com/initOS/odoo-analyse/blob/master/README.md',
        'Usage': 'https://odoo-code-search.com',
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development",
    ],
)
