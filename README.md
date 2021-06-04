# odoo-analyse

Analyse tool for odoo modules

## Installation

Install the module with the ability to render graphs:
```
$ apt install cloc graphviz
$ pip3 install "odoo-analyse[graph]"
```

## Usage

```odoo_analyse --help```

### Read in modules

`--config /path/to/odoo.cfg` .. Load modules using an odoo configuration file

`--path /path/to/modules` .. Load modules within a directory

`--load /path/to/data.json` .. Load the modules from a previously stored data file

Or if you want to load the file from `stdin`:

`--load -` .. Loads the data from the module analysis directly from the `stdin`

### Save the loaded modules

`-s /path/to/data.json` .. Store the loaded modules in a file

Or if you want to output it to `stdout`:

`-s -` .. Output the loaded modules to `stdout`

### Filtering

`--modules '*'` .. Only show modules with a matching name

`--models '*'` .. Only show models with a matching name

`--views '*'` .. Only show views with a matching name

`--path-filter '*'` .. Only modules with a matching file path

`--test-filter` .. Include module starting with `test_`

`--state-filter installed` .. Only modules with a specific state. This connects to a database to determine the state of a module. The connection information are extracted from a configuration file or using the database parameters

`--full-graph` .. If set all the above filters are only used for the starting nodes and not for the base modules

### Module graph

Use atleast one of the following `--show-*` options to show a module graph.

`--show-dependency` .. Show module dependencies from the manifests

`--show-import` .. Show imports of module from other modules

`--show-reference` .. Show XML references of modules from other modules

`--migration '*'` .. Color all modules with a matching version

### Database

These options can be used to extract instance specific information about modules such as installation state to be used in filters.

`--db-host host` .. Host on which the database is running

`--db-port 5432` .. Port on which the database is running

`--db-name odoo` .. Name of the database

`--db-user user` .. Name of the user to access the database

`--db-password` .. If specified a password prompt will ask for the password to connect to the database

## Examples

### Usage as library

If you'd like to import the package and use it within a Odoo module you can add it as an import and call the options:
```python
>>> from odoo_analyse import Odoo
>>> odoo = Odoo.from_path(".")
>>> odoo["auth_session_timeout"].models
{'ir.http': <Model: ir.http>, 'ir.config_parameter': <Model: ir.config_parameter>, 'res.users': <Model: res.users>}
>>> odoo["auth_session_timeout"].manifest
{"auth_session_timeout": {"path": "/x/y/z", "name": "auth_session_timeout", ...}}
```

### Usage as command line tool

```bash
# Analyse all modules in a folder and create a module dependency graph to module.gv.pdf
$ odoo_analyse -p /path/to/modules --show-dependency

# Analyse all available modules of an Odoo instance and save it to a json file for later usage
$ odoo_analyse -c /path/to/odoo.cfg -s /path/to/cache.json
```

The following examples are using a previously created cache file.

```bash
# Create the dependency graph of all modules starting with `sale_`
$ odoo_analyse -l /path/to/cache.json --modules 'sale_*' --show-dependency

# Create the full dependency graph of all modules starting with `sale_`
$ odoo_analyse -l /path/to/cache.json --modules 'sale_*' --show-dependency --full-graph

# Connect to the database from the odoo.cfg and create the dependency graph of all installed modules
$ odoo_analyse -l /path/to/cache.json -c /path/to/odoo.cfg --state-filter installed --show-dependency
```
