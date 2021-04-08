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

### Save the loaded modules

`-s /path/to/data.json` .. Store the loaded modules in a file

### Filtering

`--modules '*'` .. Only show modules with a matching name

`--models '*'` .. Only show models with a matching name

`--views '*'` .. Only show views with a matching name

`--path-filter '*'` .. Only modules with a matching file path

`--test-filter` .. Include module starting with `test_`

`--state-filter` .. Only modules with a specific state. This connects to a database to determine the state of a module. The connection information are extracted from a configuration file or using the database parameters

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
