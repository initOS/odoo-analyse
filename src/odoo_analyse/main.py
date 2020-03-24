#!/usr/bin/env python3
# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import argparse
import logging
import os
import sys

from .odoo import Odoo

RED, GREEN, YELLOW, BLUE, WHITE, DEFAULT = 1, 2, 3, 4, 7, 9
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLOR_PATTERN = "%s%s%%s%s" % (COLOR_SEQ, COLOR_SEQ, RESET_SEQ)
LEVEL_COLOR_MAPPING = {
    logging.DEBUG: (BLUE, DEFAULT),
    logging.INFO: (GREEN, DEFAULT),
    logging.WARNING: (YELLOW, DEFAULT),
    logging.ERROR: (RED, DEFAULT),
    logging.CRITICAL: (WHITE, RED),
}

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
    parser.add_argument("path")
    parser.add_argument(
        "--no-config",
        action="store_true",
        default=False,
        help="The path specifies a folder and not a configuration file",
    )
    parser.add_argument(
        "--path-filter",
        type=str,
        default="*",
        help="Filter out modules which paths aren't matching the glob",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="*",
        help="Filter out models which names aren't matching the glob",
    )
    parser.add_argument(
        "--modules",
        type=str,
        default="*",
        help="Filter out modules which names aren't matching the glob",
    )
    parser.add_argument(
        "--views",
        type=str,
        default="*",
        help="Filter out views which names aren't matching the glob",
    )
    parser.add_argument(
        "--tests-filter",
        action="store_true",
        default=False,
        help="Include testing modules starting with test_",
    )
    parser.add_argument(
        "--analyse",
        type=str,
        default="",
        help="Analyse the modules and store it in the given file",
    )
    parser.add_argument(
        "--dependency-graph",
        action="store_true",
        default=False,
        help="Show the module dependency of the manifest in the module graph",
    )
    parser.add_argument(
        "--import-graph",
        action="store_true",
        default=False,
        help="Show python imports in the module graph",
    )
    parser.add_argument(
        "--reference-graph",
        action="store_true",
        default=False,
        help="Show xml references in the module graph",
    )
    parser.add_argument(
        "--migration",
        type=str,
        default="*",
        help="Color the migration status in the module graph. "
        "Must be a glob which matches all migrated versions",
    )
    parser.add_argument(
        "--model-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the models",
    )
    parser.add_argument(
        "--view-graph",
        action="store_true",
        default=False,
        help="Show the dependency graph of the views",
    )
    parser.add_argument(
        "--structure-graph",
        action="store_true",
        default=False,
        help="Show the module structure graph",
    )
    parser.add_argument(
        "--full-graph",
        action="store_true",
        default=False,
        help="Show the full name and only use the filters for the starting nodes",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Set the log level. Possible values: CRITICAL, DEBUG, ERROR, "
        "INFO and WARNING",
    )
    return parser.parse_args()


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        fg, bg = LEVEL_COLOR_MAPPING.get(record.levelno, (GREEN, DEFAULT))
        record.levelname = COLOR_PATTERN % (30 + fg, 40 + bg, record.levelname)
        return logging.Formatter.format(self, record)


def main():
    args = parse_args()

    logging.addLevelName(25, "INFO")
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"

    handler = logging.StreamHandler(sys.stdout)

    formatter = ColoredFormatter(fmt)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(args.log_level)

    # Load the odoo configuration and the options
    if args.no_config and not os.path.isdir(args.path):
        _logger.critical("Path %s is not a directory", args.path)
        sys.exit(1)

    if not args.no_config and not os.path.isfile(args.path):
        _logger.critical("Path %s is not a file", args.path)
        sys.exit(1)

    if args.no_config:
        odoo = Odoo.frompath(args.path)
    else:
        odoo = Odoo.fromconfig(args.path)

    if args.full_graph:
        odoo.show_full_dependency = True

    # Apply the filters
    if not args.tests_filter:
        odoo.test_filter()
    odoo.path_filter(args.path_filter)

    # Execute the analysis
    if args.analyse and args.no_config:
        _logger.critical("Use an odoo configuration file for the analyse")
        sys.exit(1)

    if args.analyse:
        odoo.analyse(args.analyse)

    # Render the module graph if needed
    if args.dependency_graph or args.import_graph or args.reference_graph:
        odoo.show_module_graph(
            args.modules,
            args.migration,
            args.dependency_graph,
            args.import_graph,
            args.reference_graph,
        )

    # Render the strucutre graph
    if args.structure_graph:
        odoo.show_structure_graph(args.modules, args.models, args.views)

    # Render the model graph
    if args.model_graph:
        odoo.show_model_graph(args.models)

    # Render the view graph
    if args.view_graph:
        odoo.show_view_graph(args.views)


if __name__ == "__main__":
    main()
