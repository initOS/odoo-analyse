#!/usr/bin/env python3
# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import argparse
import glob
import logging
import os
import sys
from getpass import getpass

from .odoo import Odoo

try:
    import graphviz
except ImportError:
    graphviz = None


try:
    import psycopg2
except ImportError:
    psycopg2 = None


_logger = logging.getLogger(__name__)


def ensure_module(name, module):
    """Exit if module isn't installed"""
    if module is None:
        print("Python module %s isn't installed" % name)
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Default color encoding for the module graph:\n"
            " * Green: Migrated module where all dependencies are migrated\n"
            " * Orange: Migrated module where not all dependencies are migrated\n"
            " * Blue: Not migrated module where all dependencies are migrated\n"
            " * Red: Edges belonging to a loop\n"
            "\n"
            "Default color encoding for the model/view graph:\n"
            " * Blue: Module without dependencies\n"
            " * Red: Edges belonging to a loop\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_argument_group("Loading/Saving")
    group.add_argument(
        "-c",
        "--config",
        default=False,
        help="Specify an odoo configuration file to load modules",
    )
    group.add_argument(
        "-p",
        "--path",
        default=[],
        action="append",
        help="Specify a path to search for odoo modules",
    )
    group.add_argument(
        "-l",
        "--load",
        default=[],
        action="append",
        help="Load from a json file. To read the data from the stdin you can use `-`",
    )
    group.add_argument(
        "-s",
        "--save",
        default=False,
        help="Save to a json file. To write the data to the stdout you can use `-`",
    )

    group = parser.add_argument_group("Filters")
    group.add_argument(
        "--path-filter",
        default="*",
        help="Filter out modules which paths aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    group.add_argument(
        "--models",
        default="*",
        help="Filter out models which names aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    group.add_argument(
        "--modules",
        default="*",
        help="Filter out modules which names aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    group.add_argument(
        "--views",
        default="*",
        help="Filter out views which names aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    group.add_argument(
        "--test-filter",
        action="store_true",
        default=False,
        help="Include testing modules starting with test_",
    )
    group.add_argument(
        "--state-filter",
        default=False,
        help="Filter modules by their state in a database. The connection information "
        "can be used for a configuration file or directly passed.",
    )

    group = parser.add_argument_group("Database")
    group.add_argument("--db_host", default=None, help="The database host")
    group.add_argument("--db_port", default=None, type=int, help="The database port")
    group.add_argument("--db_user", default=None, help="The database user")
    group.add_argument(
        "--db_password",
        default=False,
        action="store_true",
        help="Ask for the database password",
    )
    group.add_argument("--db_name", default=None, help="The name of the database")

    group = parser.add_argument_group(
        "Module graphs",
        "Generate a module dependency graph using the following options to "
        "Specify the visible dependencies",
    )
    group.add_argument(
        "--show-dependency",
        action="store_true",
        default=False,
        help="Show the module dependency of the manifest",
    )
    group.add_argument(
        "--show-import",
        action="store_true",
        default=False,
        help="Show python imports between modules",
    )
    group.add_argument(
        "--show-reference",
        action="store_true",
        default=False,
        help="Show xml references between modules",
    )
    group.add_argument(
        "--migration",
        default=False,
        help="Color the migration status in the module graph. "
        "Must be a glob which matches all migrated versions",
    )

    group = parser.add_argument_group("Model graph")
    group.add_argument(
        "--model-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the models",
    )
    group.add_argument(
        "--no-model-inherit",
        action="store_true",
        default=False,
        help="Don't use inherit in the dependency graph of the models",
    )
    group.add_argument(
        "--no-model-inherits",
        action="store_true",
        default=False,
        help="Don't use inherits in the dependency graph of the models",
    )

    group = parser.add_argument_group("View graph")
    group.add_argument(
        "--view-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the views",
    )
    group.add_argument(
        "--no-view-inherit",
        action="store_true",
        default=False,
        help="Don't use inherit in the dependency graph of the views",
    )
    group.add_argument(
        "--no-view-call",
        action="store_true",
        default=False,
        help="Don't use t-calls in the dependency graph of the views",
    )

    group = parser.add_argument_group("Stucture graph")
    group.add_argument(
        "--structure-graph",
        action="store_true",
        default=False,
        help="Show the structure of the modules",
    )

    group = parser.add_argument_group("Misc")
    group.add_argument(
        "--analyse",
        default="",
        help="Analyse the modules and store it in the given file. "
        "To output to the stdout you can use `-`",
    )
    group.add_argument(
        "--analyse-output",
        default="json",
        choices=("csv", "json"),
        help="The format the analyse will use. Default is %(default)s",
    )
    group.add_argument(
        "-i",
        "--interactive",
        default=False,
        action="store_true",
        help="Enter the interactive mode",
    )

    group = parser.add_argument_group("Options")
    group.add_argument(
        "--verbose",
        default=False,
        action="store_true",
        help="Be verbose",
    )
    group.add_argument(
        "--full-graph",
        action="store_true",
        default=False,
        help="Show the full graph and only use the filters for the starting nodes",
    )
    if graphviz is not None:
        group.add_argument(
            "--renderer",
            default="dot",
            help=f"Specify the rendering engine. {graphviz.ENGINES}",
        )

    return parser.parse_args()


def main():
    args = parse_args()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger()
    logger.addHandler(handler)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load modules
    if args.config and not args.load:
        odoo = Odoo.from_config(args.config)
    else:
        odoo = Odoo()

    for load in args.load:
        odoo.load_json(load)

    for p in args.path:
        odoo.load_path(glob.glob(os.path.abspath(os.path.expanduser(p))))

    if args.interactive:
        odoo.interactive()
        sys.exit()

    # Save the modules
    if args.save:
        odoo.save_json(args.save)

    # Set global options
    if args.full_graph:
        odoo.show_full_dependency = True

    if graphviz is not None and args.renderer in graphviz.ENGINES:
        odoo.set_opt("odoo.engine", args.renderer)

    # Apply the filters
    if not args.test_filter:
        odoo.test_filter()
    odoo.path_filter(args.path_filter)

    if args.state_filter:
        ensure_module("psycopg2", psycopg2)
        odoo.state_filter(
            args.config,
            state=args.state_filter,
            host=args.db_host,
            database=args.db_name,
            user=args.db_user,
            port=args.db_port,
            password=getpass() if args.db_password else None,
        )

    if args.analyse:
        odoo.analyse(args.analyse, out_format=args.analyse_output)

    # Render the module graph if needed
    if args.show_dependency or args.show_import or args.show_reference:
        ensure_module("graphviz", graphviz)
        odoo.show_module_graph(
            args.modules,
            args.migration,
            args.show_dependency,
            args.show_import,
            args.show_reference,
        )

    # Render the structure graph
    if args.structure_graph:
        ensure_module("graphviz", graphviz)
        odoo.show_structure_graph(args.modules, args.models, args.views)

    # Render the model graph
    if args.model_graph:
        ensure_module("graphviz", graphviz)
        odoo.show_model_graph(
            args.models,
            inherit=not args.no_model_inherit,
            inherits=not args.no_model_inherits,
        )

    # Render the view graph
    if args.view_graph:
        ensure_module("graphviz", graphviz)
        odoo.show_view_graph(
            args.views,
            inherit=not args.no_view_inherit,
            calls=not args.no_view_call,
        )


if __name__ == "__main__":
    main()
