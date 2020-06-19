#!/usr/bin/env python3
# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import argparse
import glob
import logging
import os
import sys

import graphviz

from .odoo import Odoo

_logger = logging.getLogger(__name__)


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
        "-l", "--load", default=False, help="Load from a json file",
    )
    group.add_argument(
        "-s", "--save", default=False, help="Save to a json file",
    )

    group = parser.add_argument_group("Filters")
    group.add_argument(
        "--path-filter",
        default="*",
        help="Filter out modules which paths aren't matching the glob",
    )
    group.add_argument(
        "--models",
        default="*",
        help="Filter out models which names aren't matching the glob",
    )
    group.add_argument(
        "--modules",
        default="*",
        help="Filter out modules which names aren't matching the glob",
    )
    group.add_argument(
        "--views",
        default="*",
        help="Filter out views which names aren't matching the glob",
    )
    group.add_argument(
        "--test-filter",
        action="store_true",
        default=False,
        help="Include testing modules starting with test_",
    )

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
        default="*",
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
        help="Analyse the modules and store it in the given file",
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
        "--full-graph",
        action="store_true",
        default=False,
        help="Show the full graph and only use the filters for the starting nodes",
    )
    group.add_argument(
        "--renderer",
        default="dot",
        help="Specify the rendering engine. %s" % graphviz.ENGINES,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger()
    logger.addHandler(handler)

    # Load modules
    if args.config:
        odoo = Odoo.from_config(args.config)
    else:
        odoo = Odoo()

    if args.load:
        odoo.load_json(args.load)

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

    if args.renderer in graphviz.ENGINES:
        odoo.set_opt("odoo.engine", args.renderer)

    # Apply the filters
    if not args.test_filter:
        odoo.test_filter()
    odoo.path_filter(args.path_filter)

    if args.analyse:
        odoo.analyse(args.analyse)

    # Render the module graph if needed
    if args.show_dependency or args.show_import or args.show_reference:
        odoo.show_module_graph(
            args.modules,
            args.migration,
            args.show_dependency,
            args.show_import,
            args.show_reference,
        )

    # Render the structure graph
    if args.structure_graph:
        odoo.show_structure_graph(args.modules, args.models, args.views)

    # Render the model graph
    if args.model_graph:
        odoo.show_model_graph(
            args.models,
            inherit=not args.no_model_inherit,
            inherits=not args.no_model_inherits,
        )

    # Render the view graph
    if args.view_graph:
        odoo.show_view_graph(
            args.views, inherit=not args.no_view_inherit, calls=not args.no_view_call,
        )


if __name__ == "__main__":
    main()
