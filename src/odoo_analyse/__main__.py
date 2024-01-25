#!/usr/bin/env python3
# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import argparse
import glob
import logging
import os
import shutil
import sys
from getpass import getpass

from .odoo import Odoo
from .utils import folder_blacklist

try:
    import graphviz
except ImportError:
    graphviz = None


try:
    import psycopg2
except ImportError:
    psycopg2 = None


_logger = logging.getLogger(__name__)


Extensions = {
    "2to3": "Automatic porting needs 2to3 installed",
    "cloc": "Language analyse needs cloc",
    "eslintcc": "eslintcc not found. Skipping complexity for js",
}


def ensure_module(name, module):
    """Exit if module isn't installed"""
    if module is None:
        print(f"Python module {name} isn't installed")
        sys.exit(1)


def parser_load_save(parser):
    parser.add_argument(
        "-c",
        "--config",
        default=False,
        help="Specify an odoo configuration file to load modules",
    )
    parser.add_argument(
        "-p",
        "--path",
        default=[],
        action="append",
        help="Specify a path to search for odoo modules. Multiple use is supported",
    )
    parser.add_argument(
        "-l",
        "--load",
        default=[],
        action="append",
        help="Load from a json file. To read the data from the stdin you can use `-`",
    )
    parser.add_argument(
        "-s",
        "--save",
        default=False,
        help="Save to a json file. To write the data to the stdout you can use `-`",
    )


def parser_analyse(parser):
    parser.add_argument(
        "--skip-assets",
        action="store_true",
        help="Skip analysing assets",
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip analysing data/views",
    )
    parser.add_argument(
        "--skip-language",
        action="store_true",
        help="Skip analysing the language",
    )
    parser.add_argument(
        "--skip-python",
        action="store_true",
        help="Skip analysing the language",
    )
    parser.add_argument(
        "--skip-readme",
        action="store_true",
        help="Skip analysing the readme",
    )
    parser.add_argument(
        "--skip-all",
        action="store_true",
        help="Only analyse the absolute minimum",
    )


def parser_filters(parser):
    parser.add_argument(
        "--path-filter",
        default="*",
        help="Filter out modules which paths aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    parser.add_argument(
        "--models",
        default="*",
        help="Filter out models which names aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    parser.add_argument(
        "--modules",
        default="*",
        help="Filter out modules which names aren't matching the glob. "
        "Separate multiple filters by comma. Use `-` to load from stdin",
    )
    parser.add_argument(
        "--views",
        default="*",
        help="Filter out views which names aren't matching the glob. "
        "Separate multiple filters by comma",
    )
    parser.add_argument(
        "--no-test-filter",
        action="store_true",
        default=False,
        help="Include testing modules starting with test_",
    )
    parser.add_argument(
        "--estimate-state",
        action="store_true",
        default=False,
        help="Estimate the module state by the module list",
    )
    parser.add_argument(
        "--state-filter",
        default=False,
        help="Filter modules by their state in a database. The connection information "
        "can be used for a configuration file or directly passed.",
    )


def parser_database(parser):
    parser.add_argument("--db_host", default=None, help="The database host")
    parser.add_argument("--db_port", default=None, type=int, help="The database port")
    parser.add_argument("--db_user", default=None, help="The database user")
    parser.add_argument(
        "--db_password",
        default=False,
        action="store_true",
        help="Ask for the database password",
    )
    parser.add_argument("--db_name", default=None, help="The name of the database")


def parser_module_graph(parser):
    parser.add_argument(
        "--show-dependency",
        action="store_true",
        default=False,
        help="Show the module dependency of the manifest",
    )
    parser.add_argument(
        "--show-import",
        action="store_true",
        default=False,
        help="Show python imports between modules",
    )
    parser.add_argument(
        "--show-reference",
        action="store_true",
        default=False,
        help="Show xml references between modules",
    )
    parser.add_argument(
        "--migration",
        default=False,
        help="Color the migration status in the module graph. "
        "Must be a glob which matches all migrated versions",
    )
    parser.add_argument(
        "--odoo-version",
        default=None,
        help="The Odoo version which will be used to extend module versions with "
        "only `major.minor.patch` format",
    )


def parser_model_graph(parser):
    parser.add_argument(
        "--model-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the models",
    )
    parser.add_argument(
        "--no-model-inherit",
        action="store_true",
        default=False,
        help="Don't use inherit in the dependency graph of the models",
    )
    parser.add_argument(
        "--no-model-inherits",
        action="store_true",
        default=False,
        help="Don't use inherits in the dependency graph of the models",
    )


def parser_view_graph(parser):
    parser.add_argument(
        "--view-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the views",
    )
    parser.add_argument(
        "--no-view-inherit",
        action="store_true",
        default=False,
        help="Don't use inherit in the dependency graph of the views",
    )
    parser.add_argument(
        "--no-view-call",
        action="store_true",
        default=False,
        help="Don't use t-calls in the dependency graph of the views",
    )


def parser_structure_graph(parser):
    parser.add_argument(
        "--structure-graph",
        action="store_true",
        default=False,
        help="Show the structure of the modules",
    )


def parser_misc(parser):
    parser.add_argument(
        "--analyse",
        default="",
        help="Analyse the modules and store it in the given file. "
        "To output to the stdout you can use `-`",
    )
    parser.add_argument(
        "--analyse-output",
        default="json",
        choices=("csv", "json"),
        help="The format the analyse will use. Default is %(default)s",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        default=False,
        action="store_true",
        help="Enter the interactive mode",
    )


def parser_options(parser):
    parser.add_argument(
        "--verbose",
        default=False,
        action="store_true",
        help="Be verbose",
    )
    parser.add_argument(
        "--full-graph",
        action="store_true",
        default=False,
        help="Show the full graph and only use the filters for the starting nodes",
    )
    if graphviz is not None:
        parser.add_argument(
            "--renderer",
            default="dot",
            help=f"Specify the rendering engine. {graphviz.ENGINES}",
        )


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

    parser_load_save(parser.add_argument_group("Loading/Saving"))
    parser_analyse(parser.add_argument_group("Analyse Options"))
    parser_filters(
        parser.add_argument_group(
            "Filters",
            "Filters are using to hide module for the graphs and analyse output",
        )
    )
    parser_database(parser.add_argument_group("Database"))
    parser_module_graph(
        parser.add_argument_group(
            "Module graphs",
            "Generate a module dependency graph using the following options to "
            "Specify the visible dependencies",
        )
    )
    parser_model_graph(parser.add_argument_group("Model graph"))
    parser_view_graph(parser.add_argument_group("View graph"))
    parser_structure_graph(parser.add_argument_group("Stucture graph"))
    parser_misc(parser.add_argument_group("Misc"))
    parser_options(parser.add_argument_group("Options"))

    return parser.parse_args()


def main():  # noqa: C901  # pylint: disable=R0915
    args = parse_args()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger()
    logger.addHandler(handler)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Check addons
    for extension, warning in Extensions.items():
        if shutil.which(extension) is None:
            _logger.warning(warning)

    # Blacklist setup folders
    folder_blacklist({"setup"})

    # Load modules
    if args.config and not args.load:
        odoo = Odoo.from_config(args.config)
    else:
        odoo = Odoo()

    for load in args.load:
        odoo.load_json(load)

    cfg = {
        "skip_assets": args.skip_assets or args.skip_all,
        "skip_data": args.skip_data or args.skip_all,
        "skip_language": args.skip_language or args.skip_all,
        "skip_python": args.skip_python or args.skip_all,
        "skip_readme": args.skip_readme or args.skip_all,
    }

    for p in args.path:
        odoo.load_path(glob.glob(os.path.abspath(os.path.expanduser(p))), **cfg)

    if args.interactive:
        odoo.interactive()
        sys.exit()

    if args.modules == "-" and args.load == "-":
        raise ValueError("Only `--load` or `--modules` can be `-` but not both")

    if args.modules == "-":
        modules = ",".join(filter(None, (x.strip() for x in sys.stdin.readlines())))
    else:
        modules = args.modules

    if args.estimate_state:
        odoo.estimate_state(modules)

    # Save the modules
    if args.save:
        odoo.save_json(args.save)

    # Set global options
    if args.full_graph:
        odoo.show_full_dependency = True

    if graphviz is not None and args.renderer in graphviz.ENGINES:
        odoo.set_opt("odoo.engine", args.renderer)

    # Apply the filters
    if not args.no_test_filter:
        odoo.test_filter()
    odoo.path_filter(args.path_filter)

    if args.state_filter:
        if not args.estimate_state:
            ensure_module("psycopg2", psycopg2)
            odoo.load_state_from_database(
                args.config,
                host=args.db_host,
                database=args.db_name,
                user=args.db_user,
                port=args.db_port,
                password=getpass() if args.db_password else None,
            )

        odoo.state_filter(args.state_filter)

    if args.analyse:
        odoo.analyse(args.analyse, out_format=args.analyse_output)

    # Render the module graph if needed
    if args.show_dependency or args.show_import or args.show_reference:
        ensure_module("graphviz", graphviz)
        odoo.show_module_graph(
            modules,
            version=args.migration,
            depends=args.show_dependency,
            imports=args.show_import,
            refers=args.show_reference,
            odoo_version=args.odoo_version,
        )

    # Render the structure graph
    if args.structure_graph:
        ensure_module("graphviz", graphviz)
        odoo.show_structure_graph(modules, args.models, args.views)

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
