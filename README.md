# odoo-analyse

Analyse tool for odoo modules

## Installation

python3 setup.py install

## Usage

Read in an entire odoo instance and produce a dependency graph. Not recommended because time consuming.

```bash
odoo-analyse --dependency-graph /path/to/odoo.cfg
```

Read in an entire addon folder and make a dependency graph:
```bash
odoo-analyse --no-config --dependency-graph /path/to/odoo/src/
```
