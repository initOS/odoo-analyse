# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ast
import csv
import logging
import os
import re
import sys
import tempfile
from functools import partial

from lxml import etree

from .model import Model
from .utils import (
    analyse_language,
    fix_indentation,
    folder_blacklist,
    hexhash_files,
    stopwords,
    try_automatic_port,
)
from .view import View

Manifests = ["__manifest__.py", "__odoo__.py", "__openerp__.py"]
_logger = logging.getLogger(__name__)


def is_readme(filename):
    return any(filename.startswith(k) for k in ("readme.", "README."))


class Module:
    def __init__(self, path):
        # Path to the module
        self.path = path
        # Technical name of the module
        self.name = path.rstrip("/").split("/")[-1]
        # Manifest of the module
        self.manifest = {}
        # Models defined in the module
        self.models = {}
        # Views defined in the module
        self.views = {}
        # Records defined in the module
        self.data = 0
        # Modules this module depends on
        self.depends = set()
        # Modules this module imports in python files
        self.imports = set()
        # Modules this module refers to in xml files
        self.refers = set()
        # Parsed files of the module
        self.files = set()
        # Status
        self.status = set()
        self.language = {}
        # readme file, status and description
        self.words = set()
        # hash of all the modules
        self.hashsum = ""

    @property
    def author(self):
        return self.manifest.get("author", "")

    @property
    def category(self):
        return self.manifest.get("category", "")

    @property
    def description(self):
        return self.manifest.get("description", "")

    @property
    def external_dependencies(self):
        return self.manifest.get("external_dependencies", {})

    @property
    def installable(self):
        return self.manifest.get("installable", False)

    @property
    def license(self):
        return self.manifest.get("license", "")

    @property
    def readme(self):
        for f in os.listdir(self.path):
            if is_readme(f):
                p = os.path.join(self.path, f)
                return open(p, "r").read()
        return ""

    @property
    def readme_type(self):
        for f in os.listdir(self.path):
            if is_readme(f):
                return os.path.splitext(f)[1] or None
        return None

    @property
    def summary(self):
        return self.manifest.get("summary", "")

    @property
    def version(self):
        return self.manifest.get("version", "")

    @property
    def website(self):
        return self.manifest.get("website", "")

    @property
    def info(self):
        deps = self.depends.union(self.imports).union(self.refers)
        return {
            "name": self.name,
            "model_count": len(self.models),
            "data_count": self.data,
            "depends": len(deps),
        }

    def add(self, **kwargs):
        if "depends" in kwargs:
            self.depends.add(kwargs["depends"])
        if "files" in kwargs:
            self.files.add(kwargs["files"])
        if "imports" in kwargs:
            self.imports.add(kwargs["imports"])
        if "refers" in kwargs:
            self.refers.add(kwargs["refers"])

    def update(self, **kwargs):
        self.models.update(kwargs.get("models", {}))
        self.depends.update(kwargs.get("depends", []))
        self.files.update(kwargs.get("files", []))
        self.imports.update(kwargs.get("imports", []))
        self.refers.update(kwargs.get("refers", []))

    def __repr__(self):
        return "<Module: %s>" % self.name

    def analyse_language(self):
        self.language = analyse_language(self.path)

    def analyse_hash(self, files_list):
        self.hashsum = hexhash_files(files_list, self.path)

    def _load_python(self, path, filename):
        def parse_python(filepath, version=None):
            with open(filepath) as fp:
                data = fp.read()

            # Python 3.8 allows setting the feature level
            if version:
                parsed = ast.parse(data, feature_version=version)
                _logger.warning("Feature version %s %s", version, filepath)
                self.status.add("feature-%s-%s" % version)
                return parsed
            return ast.parse(data)

        def port_fix_file(filepath):
            with tempfile.NamedTemporaryFile("w+") as tmp:
                tmp.file.write(open(filepath, "r").read())
                if try_automatic_port(tmp.name):
                    _logger.warning("Ported %s", filepath)
                    self.status.add("ported")
                if fix_indentation(tmp.name):
                    _logger.warning("Fixed indentation %s", filepath)
                    self.status.add("indent-fix")
                return parse_python(tmp.name)

        versions = [None]
        if sys.version_info >= (3, 8):
            versions.append((3, 6))

        funcs = [partial(parse_python, version=ver) for ver in versions]
        funcs.append(port_fix_file)

        exc = None
        filepath = os.path.join(path, filename)
        for func in funcs:
            try:
                return func(filepath)
            except (SyntaxError, TabError) as e:
                exc = e

        _logger.error("Not parsable %s: %s", filepath, exc)
        raise exc

    def _parse_class_def(self, obj, content):
        model = Model.from_ast(obj, content)
        if not model or not model.name:
            return
        if model.name in self.models:
            self.models[model.name].update(model)
        else:
            self.models[model.name] = model

    def _parse_python(self, path, filename):
        obj = self._load_python(path, filename)

        with open(os.path.join(path, filename)) as fp:
            content = fp.read()

        self.add(files=path + filename)

        imports = set()
        fmt = "{}.{}".format
        for c in obj.body:
            if isinstance(c, ast.ImportFrom):
                m = c.module
                imports.update(fmt(m or "", name.name) for name in c.names)
            elif isinstance(c, ast.Import):
                imports.update(name.name for name in c.names)

        for child in obj.body:
            if isinstance(child, ast.ClassDef):
                self._parse_class_def(child, content)

        patterns = ["odoo.addons.", "openerp.addons."]
        for imp in imports:
            if any(imp.startswith(p) for p in patterns):
                mod = imp.split(".")[2]
                if mod != self.name:
                    self.imports.add(mod)
                continue

            if imp.split(".", 1)[0] in ["odoo", "openerp"]:
                continue

            p = path
            for f in imp.lstrip(".").split("."):
                if os.path.isfile("%s%s.py" % (p, f)):
                    self._parse_python(p, f + ".py")
                elif os.path.isfile("%s%s/__init__.py" % (p, f)):
                    self._parse_python("%s%s/" % (p, f), "__init__.py")
                elif os.path.isdir(p + f):
                    p += f + "/"
                else:
                    break

    def _parse_manifest(self, path):
        with open(path) as fp:
            obj = ast.literal_eval(fp.read())
            if isinstance(obj, dict):
                self.update(depends=obj.get("depends", []), files=obj.get("data", []))
                self.manifest.update(obj)
                self._parse_text_for_keywords(
                    [self.name, self.summary, self.description]
                )

    def _parse_csv(self, path):
        if not os.path.isfile(path):
            self.status.add("missing-file")
            return

        with open(path) as fp:
            obj = csv.reader(fp)
            self.data += max(0, obj.line_num - 1)

    def _parse_xml(self, path):
        if not os.path.isfile(path):
            self.status.add("missing-file")
            return

        obj = etree.parse(path)
        # Supported special tags defining data
        tags = [
            "act_window",
            "assert",
            "delete",
            "function",
            "menuitem",
            "record",
            "report",
            "template",
            "url",
        ]
        self.data += sum(len(obj.xpath("//%s" % tag)) for tag in tags)

        # xpaths to get all referred modules
        xpaths = [
            "//record/field[@name='inherit_id']/@ref",
            "//template/@inherit_id",
            "//record[@model='ir.ui.view']/field[@name='arch']//@t-call",
            "//template//@t-call",
        ]
        xpaths.extend("//%s/@id" % tag for tag in tags)

        xmlid = re.compile(r"\w+\.\w+")
        xpaths = " | ".join(xpaths)
        refs = {x.split(".")[0] for x in obj.xpath(xpaths) if xmlid.match(x)}
        self.refers.update({x for x in refs if x != self.name})

        # xpaths to extract views
        for node in obj.xpath("//record[@model='ir.ui.view'] | //template"):
            view = View.from_xml(self.name, node)
            if not view:
                continue

            if view.name in self.views:
                self.views[view.name].update(view)
            else:
                self.views[view.name] = view

    def _parse_text_for_keywords(self, texts):
        if not isinstance(texts, list):
            texts = [texts]

        words = stopwords()
        for text in texts:
            tmp = {w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", text)}
            self.words |= tmp.difference(words)

    def _parse_readme(self, path):
        with open(path) as fp:
            self._parse_text_for_keywords(fp.read())

    def to_json(self):
        return {
            "path": self.path,
            "name": self.name,
            "manifest": self.manifest,
            "models": {n: m.to_json() for n, m in self.models.items()},
            "views": {n: v.to_json() for n, v in self.views.items()},
            "data": self.data,
            "depends": list(self.depends),
            "imports": list(self.imports),
            "refers": list(self.refers),
            "files": list(self.files),
            "status": list(self.status),
            "language": self.language,
            "words": list(self.words),
            "hashsum": self.hashsum,
        }

    @classmethod
    def from_json(cls, data):
        module = cls(data.get("path"))
        module.name = data["name"]
        module.manifest = data["manifest"]
        module.models = {n: Model.from_json(m) for n, m in data["models"].items()}
        module.views = {n: View.from_json(m) for n, m in data["views"].items()}
        module.data = data["data"]
        module.depends = set(data["depends"])
        module.imports = set(data["imports"])
        module.refers = set(data["refers"])
        module.files = set(data["files"])
        module.status = set(data["status"])
        module.language = data["language"]
        module.words = set(data["words"])
        module.hashsum = data["hashsum"]
        return module

    @classmethod
    def from_path(cls, path):
        files_list = []
        module = cls(path)
        found_init, found_manifest = False, 0
        if not path.endswith("/"):
            path += "/"

        # Find the manifest scripts
        for f in Manifests:
            filepath = os.path.join(path, f)
            if os.path.isfile(filepath):
                found_manifest += 1
                module._parse_manifest(filepath)

        if not found_manifest:
            return None

        if found_manifest > 1:
            module.status.add("mutiple-manifest")

        for f in os.listdir(path):
            # Found the init script
            if f == "__init__.py":
                found_init = True
                module._parse_python(path, f)

            # Found the readme
            elif is_readme(f):
                module._parse_readme(path + f)

            filepath = os.path.join(path, f)
            if os.path.isfile(filepath):
                files_list.append(filepath)

        if not found_init:
            return None

        module.analyse_language()

        for file in module.files:
            file_path = os.path.join(path, file)
            files_list.append(file_path)
            if file.endswith(".xml"):
                module._parse_xml(file_path)
            elif file.endswith(".csv"):
                module._parse_csv(file_path)

        module.analyse_hash(files_list)

        _logger.info("Found module %s", module.name)
        if module.status:
            _logger.info("Status %s: %s", module.name, module.status)

        return module

    @classmethod
    def find_modules_iter(cls, paths, depth=None):
        result = {}
        if isinstance(paths, str):
            paths = [paths]

        paths = [(p, 0) for p in paths]
        blacklist = folder_blacklist()
        # Breadth-first search
        while paths:
            path, d = paths.pop(0)
            path = path.strip()
            if depth is not None and d > depth:
                continue

            try:
                module = cls.from_path(path)
            except Exception as e:
                _logger.exception(e)
                continue

            if module is not None:
                name = module.name
                if name not in result:
                    yield name, module
            else:
                sub_paths = [
                    os.path.join(path, p)
                    for p in os.listdir(path)
                    if p not in blacklist
                ]
                paths.extend((p, d + 1) for p in sub_paths if os.path.isdir(p))

    @classmethod
    def find_modules(cls, paths, depth=None):
        return dict(cls.find_modules_iter(paths, depth))
