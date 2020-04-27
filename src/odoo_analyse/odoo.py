# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
import os
from configparser import ConfigParser
from fnmatch import fnmatch
from functools import reduce

try:
    from graphviz import Digraph, Graph
except ImportError:
    Digraph = Graph = None

from .module import Module

_logger = logging.getLogger(__name__)


class Odoo:
    def __init__(self, config="analyse.cfg", modules=None, filters=None):
        self.load_config(config)
        self.full = modules or {}
        self.modules = modules or {}
        self.filters = filters or []

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
        _logger.debug("Applying filter: test")
        self.modules = {
            name: module
            for name, module in self.items()
            if not name.startswith("test_")
        }

    def path_filter(self, pattern):
        _logger.debug("Applying filter: path [%s]", pattern)
        self.modules = {
            name: module
            for name, module in self.items()
            if fnmatch(module.path, pattern)
        }

    def name_filter(self, pattern):
        _logger.debug("Applying filter: name [%s]", pattern)
        self.modules = {
            name: module for name, module in self.items() if fnmatch(name, pattern)
        }

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
        try:
            from IPython import start_ipython

            start_ipython(argv=[], user_ns=local_vars)
        except ImportError:
            from code import interact

            banner = ["%s: %s" % pair for pair in sorted(local_vars.items())]
            interact("\n".join(banner), local=local_vars)

    def analyse(self, file_path):
        _logger.debug("Start analysing...")
        models = {
            mname: name
            for name, module in self.full.items()
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
                "data_count": module.data,
                "depends": sorted(module.depends),
                "fields": fields,
                "imports": sorted(module.imports),
                "model_count": len(module.models),
                "refers": sorted(used),
            }
            if missing:
                _logger.error("Missing dependency: %s -> %s", name, missing)
                res[name]["missing_dependency"] = sorted(missing)

        if file_path == "-":
            print(json.dumps(res, indent=2))
        else:
            with open(file_path, "w+") as fp:
                json.dump(res, fp, indent=2)

    def load_path(self, paths, depth=None):
        if isinstance(paths, str):
            paths = [paths]

        result = Module.find_modules(paths, depth=depth)

        self.full = result.copy()
        self.modules = result.copy()

    def load_json(self, filename):
        with open(filename) as fp:
            data = json.load(fp)

            self.modules = {k: Module.from_json(v) for k, v in data.items()}
            self.full = self.modules.copy()

    def save_json(self, filename):
        with open(filename, "w+") as fp:
            json.dump({k: m.to_json() for k, m in self.full.items()}, fp)

    def _find_edges_in_loop(self, graph):
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
        self, graph, node_check=None, color_node=None, color_edge=None, filename=None,
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
        if self.opt("odoo.show_full_dependency"):
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

        if not visible:
            return

        output = Digraph(engine=self.opt("odoo.engine", "dot"))
        for name in visible:
            depends = graph[name]
            if callable(color_node):
                output.node(name, color=color_node(name))
            else:
                output.node(name)

            for dep in depends:
                if dep not in visible:
                    continue

                if callable(color_edge):
                    output.edge(name, dep, color=color_edge(name, dep))
                else:
                    output.edge(name, dep)

        self._show_output(output, filename=filename)

    def _show_output(self, graph, filename):
        graph.view(filename=filename)

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
                field_id = "%s/%s" % (model_id, field_name)
                output.node(
                    field_id, label=field_name, color=field_color, shape=field_shape
                )
                output.edge(model_id, field_id)

        def render_model(module_id, model_name, model):
            model_id = "%s/%s" % (module_id, model_name)
            output.node(
                model_id, label=model_name, color=model_color, shape=model_shape
            )
            output.edge(module_id, model_id)

            if fields:
                render_field(model_id, model)

        def render_view(module_id, view_name, view):
            view_id = "%s/%s" % (module_id, view_name)
            output.node(view_id, label=view_name, color=view_color, shape=view_shape)
            output.edge(module_id, view_id)

        for module_name, module in self.items():
            if not fnmatch(module_name, modules):
                continue

            module_id = module_name
            output.node(
                module_id, label=module_name, color=module_color, shape=module_shape,
            )

            for model_name, model in module.models.items():
                if fnmatch(model_name, models):
                    render_model(module_id, model_name, model)

            for view_name, view in module.views.items():
                if fnmatch(view_name, views):
                    render_view(module_id, view_name, view)

        self._show_output(output, filename=filename or "structure.gv")

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
        graph = {}
        for name, module in self.items():
            graph[name] = set()
            if depends:
                graph[name].update(module.depends)
            if imports:
                graph[name].update(module.imports)
            if refers:
                graph[name].update(module.refers)

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
            return fnmatch(node, modules)

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
            graph, check_node, color_node, color_edge, filename=filename or "module.gv",
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
            return fnmatch(node, models)

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
            return fnmatch(node, views)

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
