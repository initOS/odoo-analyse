# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import csv
import json
import logging
import os
import sys
from configparser import ConfigParser
from fnmatch import fnmatch
from functools import reduce

from .module import Module

try:
    from graphviz import Digraph, Graph
except ImportError:
    Digraph = Graph = None

try:
    from psycopg2 import connect
except ImportError:
    connect = None


_logger = logging.getLogger(__name__)


def match(s, patterns):
    return any(fnmatch(s, x) for x in patterns.split(","))


class Odoo:
    def __init__(self, config="analyse.cfg", modules=None, filters=None):
        self.load_config(config)
        self.full = modules or {}
        self.modules = modules or {}
        self.filters = filters or []
        self.show_full_dependency = False

    @classmethod
    def from_config(cls, config_path):
        if not os.path.isfile(config_path):
            return None

        odoo = cls()
        odoo.load(config_path)
        return odoo

    @classmethod
    def from_path(cls, path):
        if not os.path.isdir(path):
            return None

        odoo = cls()
        odoo.load_path(path)
        return odoo

    def __len__(self):
        return len(self.modules)

    def __iter__(self):
        return iter(self.modules)

    def __contains__(self, name):
        return name in self.modules

    def __getitem__(self, name):
        return self.modules[name]

    def load_config(self, file):
        self.config = {}
        if not os.path.isfile(file):
            return

        cp = ConfigParser()
        cp.read(file)

        for section_name, section in cp.items():
            self.config[section_name] = dict(section)
            for option_name, value in section.items():
                key = "%s.%s" % (section_name, option_name)
                self.config[key] = value

    def set_opt(self, option, value):
        self.config[option] = value

    def opt(self, name, default=None):
        return self.config.get(name, default) or None

    def items(self):
        return self.modules.items()

    def models(self):
        res = {}
        for module in self.modules.values():
            for model in module.models.values():
                if model.name in res:
                    res[model.name].update(model)
                else:
                    res[model.name] = model.copy()
        return res

    def views(self):
        res = {}
        for module in self.modules.values():
            for view in module.views.values():
                if view.name in res:
                    res[view.name].update(view)
                else:
                    res[view.name] = view.copy()
        return res

    def test_filter(self):
        """Filter out modules starting with test_"""
        _logger.debug("Applying filter: test")
        self.modules = {
            name: module
            for name, module in self.items()
            if not name.startswith("test_")
        }

    def path_filter(self, pattern):
        """Filter the modules using their paths"""
        _logger.debug("Applying filter: path [%s]", pattern)
        self.modules = {
            name: module for name, module in self.items() if match(module.path, pattern)
        }

    def name_filter(self, pattern):
        """Filter the modules using their names"""
        _logger.debug("Applying filter: name [%s]", pattern)
        self.modules = {
            name: module for name, module in self.items() if match(name, pattern)
        }

    def state_filter(self, config_path=None, state="installed", **kwargs):
        """Filter the modules by their states in a database"""

        _logger.debug("Applying filter: state [%s]", state)

        def adapt(val):
            if val.lower() in ("false", "none", ""):
                return None
            try:
                return int(val)
            except ValueError:
                return val

        args = {
            "host": None,
            "database": None,
            "user": None,
            "password": None,
            "port": None,
        }

        # Load the database connection from a configuration file
        if config_path:
            cp = ConfigParser()
            cp.read(config_path)

            args.update(
                {
                    "host": adapt(cp.get("options", "db_host", fallback=None)),
                    "port": adapt(cp.get("options", "db_port", fallback=None)),
                    "database": adapt(cp.get("options", "db_name", fallback=None)),
                    "user": adapt(cp.get("options", "db_user", fallback=None)),
                    "password": adapt(cp.get("options", "db_password", fallback=None)),
                }
            )

        # Overwrite if parameters are specified manually
        args.update((k, v) for k, v in kwargs.items() if k in args and v)

        # Clear the arguments a bit. Without password assumes a local database
        args = {k: v for k, v in args.items() if v}
        if "password" not in args:
            args.pop("host", None)

        # Connect to the database and fetch the modules in the given state
        with connect(**args) as db:
            cr = db.cursor()
            cr.execute("SELECT name FROM ir_module_module WHERE state = %s", (state,))
            names = {row[0] for row in cr.fetchall()}

        # Apply the filter
        self.modules = {name: module for name, module in self.items() if name in names}

    def load(self, config_path):
        _logger.debug("Reading odoo configuration file")
        cp = ConfigParser()
        cp.read(config_path)

        paths = cp.get("options", "addons_path", fallback="").split(",")
        self.load_path(paths, depth=1)

    def _full_dependency(self, name):
        if name not in self:
            return set()

        res = set()
        mods = list(self[name].depends)
        while mods:
            mod = mods.pop()
            if mod not in res and mod in self.full:
                res.add(mod)
                mods.extend(self.full[mod].depends)
        return res

    def interactive(self):
        local_vars = {"analyse": self}
        # pylint: disable=C0415
        try:
            from IPython import start_ipython

            start_ipython(argv=[], user_ns=local_vars)
        except ImportError:
            from code import interact

            banner = [f"{name}: {obj}" for name, obj in sorted(local_vars.items())]
            interact("\n".join(banner), local=local_vars)

    def analyse(self, file_path, out_format="json"):
        """Return some analyse data about every module"""
        _logger.debug("Start analysing...")
        models = {
            mname: name
            for name, module in self.items()
            for mname, model in module.models.items()
            if not model.inherit and not model.inherits
        }

        res = {}
        for name, module in self.items():
            fields = 0
            used = module.imports.union(module.refers)
            for model in module.models.values():
                fields += len(model.fields)

                used.union({models[x] for x in model.inherit if x in models})
                used.union({models[x] for x in model.inherits if x in models})

            full = self._full_dependency(name)
            missing = used.difference(full)
            missing.discard("base")

            res[name] = {
                "record_count": len(module.records),
                "depends": sorted(module.depends),
                "fields": fields,
                "imports": sorted(module.imports),
                "model_count": len(module.models),
                "refers": sorted(used),
                "path": module.path,
                "language": {k: v["lines"] for k, v in module.language.items()},
                "license": module.license,
                "author": module.author,
                "category": module.category,
                "version": module.version,
                "status": list(module.status),
            }
            if missing:
                _logger.error("Missing dependency: %s -> %s", name, missing)
                res[name]["missing_dependency"] = sorted(missing)

        if out_format == "csv":
            self._analyse_out_csv(res, file_path)
        else:
            self._analyse_out_json(res, file_path)

    def _analyse_out_csv(self, data, file_path):  # pylint: disable=R0201
        """Output the analyse result as CSV"""
        fields = {"name"}
        rows = []

        for name, module in data.items():
            tmp = {"name": name}
            for key, value in module.items():
                if isinstance(value, dict):
                    for k, v in value.items():
                        tmp[f"{key}/{k}"] = v
                elif isinstance(value, list):
                    tmp[key] = ",".join(value)
                else:
                    tmp[key] = str(value)

            fields.update(tmp)
            rows.append(tmp)

        # pylint: disable=E0012,R1732
        fp = sys.stdout if file_path == "-" else open(file_path, "w+", encoding="utf-8")
        writer = csv.DictWriter(fp, sorted(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    def _analyse_out_json(self, data, file_path):  # pylint: disable=R0201
        """Output the analyse result as JSON"""
        # Write to a file or stdout
        if file_path == "-":
            json.dump(data, sys.stdout, indent=2)
        else:
            with open(file_path, "w+", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    def load_path(self, paths, depth=None):
        if isinstance(paths, str):
            paths = [paths]

        result = Module.find_modules(paths, depth=depth)

        self.full.update(result.copy())
        self.modules.update(result.copy())

    def load_json(self, filename):
        if filename == "-":
            data = json.load(sys.stdin)
        else:
            with open(filename, encoding="utf-8") as fp:
                data = json.load(fp)

        self.modules.update({k: Module.from_json(v) for k, v in data.items()})
        self.full = self.modules.copy()

    def save_json(self, filename):
        data = {k: m.to_json() for k, m in self.full.items()}
        if filename == "-":
            json.dump(data, sys.stdout)
        else:
            with open(filename, "w+", encoding="utf-8") as fp:
                json.dump(data, fp)

    def _find_edges_in_loop(self, graph):  # pylint: disable=R0201
        # Eliminate not referenced and not referring modules
        while True:
            before = len(graph)

            tmp = {k: v.intersection(graph) for k, v in graph.items()}
            deps = reduce(lambda a, b: a.union(b), tmp.values(), set())
            graph = {k: v for k, v in tmp.items() if v and k in deps}

            after = len(graph)
            if before == after:
                break

        return {(a, b) for a, bs in graph.items() for b in bs}

    def _show_graph(
        self,
        graph,
        node_check=None,
        color_node=None,
        color_edge=None,
        filename=None,
    ):
        if not graph:
            return

        # Don't show nodes without dependencies
        if self.opt("odoo.skip_lonely_node", True):
            depends = reduce(lambda a, b: a.union(b), graph.values(), set())
            depends.intersection_update(graph)

            tmp, graph = graph.copy(), {}
            for name, deps in tmp.items():
                deps.intersection_update(depends)
                if deps or name in depends:
                    graph[name] = deps

        # Set the visible nodes
        if callable(node_check):
            visible = set(filter(node_check, graph))
        else:
            visible = set(graph)

        # Show all dependency ignoring the filters
        highlight = set()
        if self.opt("odoo.show_full_dependency") or self.show_full_dependency:
            nodes = list(visible)
            visited = set()
            while nodes:
                current = nodes.pop()
                if current in visited:
                    continue
                visited.add(current)

                depends = graph[current]
                visible.update(depends)
                nodes.extend(depends)

            # Extend the auto install
            current, previous = len(visible), None
            while current != previous:
                for name, module in self.full.items():
                    if (
                        module.auto_install
                        and module.depends.issubset(visible)
                        and name not in visible
                    ):
                        visible.add(name)
                        highlight.add(name)
                current, previous = len(visible), current

        if not visible:
            return

        output = Digraph(engine=self.opt("odoo.engine", "dot"))
        for name in visible:
            depends = graph[name]
            style = "dashed" if name in highlight else None
            if callable(color_node):
                output.node(name, color=color_node(name), style=style)
            else:
                output.node(name, style=style)

            for dep in depends:
                if dep not in visible:
                    continue

                if callable(color_edge):
                    output.edge(name, dep, color=color_edge(name, dep))
                else:
                    output.edge(name, dep)

        self._show_output(output, filename=filename)

    def _show_output(self, graph, filename):  # pylint: disable=R0201
        graph.render(filename=filename)

    def show_structure_graph(
        self, modules="*", models="*", views="*", fields=True, filename=None
    ):
        module_color = self.opt("structure.module_color")
        module_shape = self.opt("structure.module_shape", "doubleoctagon")
        model_color = self.opt("structure.model_color")
        model_shape = self.opt("structure.model_shape", "box")
        view_color = self.opt("structure.view_color")
        view_shape = self.opt("structure.view_shape", "oval")
        field_color = self.opt("structure.field_color")
        field_shape = self.opt("structure.field_shape", "octagon")

        output = Graph()

        def render_field(model_id, model):
            for field_name in model.fields:
                field_id = f"{model_id}/{field_name}"
                output.node(
                    field_id, label=field_name, color=field_color, shape=field_shape
                )
                output.edge(model_id, field_id)

        def render_model(module_id, model_name, model):
            model_id = f"{module_id}{model_name}"
            output.node(
                model_id, label=model_name, color=model_color, shape=model_shape
            )
            output.edge(module_id, model_id)

            if fields:
                render_field(model_id, model)

        def render_view(module_id, view_name, _view):
            view_id = f"{module_id}/{view_name}"
            output.node(view_id, label=view_name, color=view_color, shape=view_shape)
            output.edge(module_id, view_id)

        for module_name, module in self.items():
            if not match(module_name, modules):
                continue

            module_id = module_name
            output.node(
                module_id,
                label=module_name,
                color=module_color,
                shape=module_shape,
            )

            for model_name, model in module.models.items():
                if match(model_name, models):
                    render_model(module_id, model_name, model)

            for view_name, view in module.views.items():
                if match(view_name, views):
                    render_view(module_id, view_name, view)

        self._show_output(output, filename=filename or "structure.gv")

    def _build_module_graph(self, depends, imports, refers):
        graph = {}
        for name, module in self.items():
            graph[name] = set()
            if depends:
                graph[name].update(module.depends)
            if imports:
                graph[name].update(module.imports)
            if refers:
                graph[name].update(module.refers)

        return graph

    def show_module_graph(
        self,
        modules="*",
        version=False,
        depends=True,
        imports=False,
        refers=False,
        filename=None,
    ):
        # Build the dependency graph
        graph = self._build_module_graph(depends, imports, refers)

        # Detect loops
        loop_edges = self._find_edges_in_loop(graph)
        # Evaluate the migration state if possible
        if version:
            migrated = {name for name, module in self.items()}
            fully_migrated = {
                name
                for name, mod in self.items()
                if all(dep in migrated for dep in mod.depends if dep in self)
            }
        else:
            migrated = fully_migrated = set()

        # Options
        done_color = self.opt("module.done_color", "green")
        todo_color = self.opt("module.todo_color", "blue")
        warning_color = self.opt("module.warning_color", "orange")
        default_color = self.opt("module.default_color")
        loop_color = self.opt("module.loop_color", "red")

        def check_node(node):
            return match(node, modules)

        # Coloring functions
        def color_node(node):
            if node in migrated and node in fully_migrated:
                return done_color
            if node in fully_migrated:
                return todo_color
            if node in migrated:
                return warning_color
            return default_color

        def color_edge(node_a, node_b):
            if (node_a, node_b) in loop_edges:
                return loop_color
            return None

        # Show the resulting graph
        self._show_graph(
            graph,
            check_node,
            color_node,
            color_edge,
            filename=filename or "module.gv",
        )

    def show_model_graph(self, models="*", inherit=True, inherits=True, filename=None):
        graph = {}
        for name, model in self.models().items():
            graph[name] = set()

            if inherit:
                graph[name].update(model.inherit)
            if inherits:
                graph[name].update(model.inherits)

        # Detect loops
        loop_edges = self._find_edges_in_loop(graph)

        # Options
        base_color = self.opt("model.base_color", "blue")
        default_color = self.opt("model.default_color")
        loop_color = self.opt("model.loop_color", "red")

        def check_node(node):
            return match(node, models)

        # Coloring functions
        def color_node(node):
            if not graph.get(node, True):
                return base_color
            return default_color

        def color_edge(node_a, node_b):
            if (node_a, node_b) in loop_edges:
                return loop_color
            return None

        self._show_graph(
            graph, check_node, color_node, color_edge, filename=filename or "model.gv"
        )

    def show_view_graph(self, views="*", inherit=True, calls=True, filename=None):
        """Show the graph of the views"""
        graph = {}
        for name, view in self.views().items():
            graph[name] = set()

            if inherit:
                graph[name].add(view.inherit)
            if calls:
                graph[name].update(view.calls)

        # Detect loops
        loop_edges = self._find_edges_in_loop(graph)

        # Options
        base_color = self.opt("view.base_color", "blue")
        default_color = self.opt("view.default_color")
        loop_color = self.opt("view.loop_color", "red")

        def check_node(node):
            return match(node, views)

        # Coloring functions
        def color_node(node):
            if not graph.get(node, True):
                return base_color
            return default_color

        def color_edge(node_a, node_b):
            if (node_a, node_b) in loop_edges:
                return loop_color
            return None

        self._show_graph(
            graph, check_node, color_node, color_edge, filename=filename or "view.gv"
        )
