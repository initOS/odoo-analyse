import os

from setuptools import find_packages, setup


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


setup(
    name="odoo-analyse",
    version="1.0.1",
    author="initOS GmbH",
    author_email="info@initos.com",
    description="Package to analyse odoo modules",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="LGPL-3.0",
    keywords="odoo, modules, analyze, dependency, graph",
    url="https://github.com/initOS/odoo-analyse",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_name="odoo-analyse",
    include_package_data=True,
    entry_points={"console_scripts": ["odoo_analyse = odoo_analyse.main:main"]},
    python_requires=">=3.5",
    install_requires=["2to3", "cloc", "lxml"],
    extras_require={"graph": ["graphviz", "psycopg2"]},
    project_urls={
        "Documentation": "https://github.com/initOS/odoo-analyse/blob/master/README.md",
        "Usage": "https://odoo-code-search.com",
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Topic :: Software Development",
    ],
)
