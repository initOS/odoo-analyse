# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import ast
import glob
import logging
import os
import re
import sys
import tempfile
import time
from functools import partial
from pathlib import Path

from lxml import etree

from .js_module import JSModule
from .model import Model
from .record import Record
from .utils import (
    analyse_language,
    fix_indentation,
    folder_blacklist,
    hexhash_files,
    stopwords,
    try_automatic_port,
)

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
        # Additional defined classes in the module
        self.classes = {}
        # JS modules
        self.js_modules = {}
        # Views defined in the module
        self.views = {}
        # Records (non views) defined in the module
        self.records = {}
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
        self.duration = 0
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
    def auto_install(self):
        return self.manifest.get("auto_install", False)

    @property
    def license(self):
        return self.manifest.get("license", "")

    @property
    def readme(self):
        for f in os.listdir(self.path):
            if not is_readme(f):
                continue

            p = os.path.join(self.path, f)
            with open(p, "r", encoding="utf-8") as fp:
                return fp.read()
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
            "class_count": len(self.classes),
            "record_count": len(self.records),
            "view_count": len(self.views),
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
        return f"<Module: {self.name}>"

    def analyse_language(self):
        self.language = analyse_language(self.path)

    def analyse_hash(self, files_list):
        self.hashsum = hexhash_files(files_list, self.path)

    def _load_python(self, path, filename):
        def parse_python(filepath, version=None):
            with open(filepath, encoding="utf-8") as fp:
                data = fp.read()

            # Python 3.8 allows setting the feature level
            if version:
                parsed = ast.parse(data, feature_version=version)
                _logger.warning("Feature version %s %s", version, filepath)
                self.status.add(f"feature-{version[0]}-{version[1]}")
                return parsed
            return ast.parse(data)

        def port_fix_file(filepath):
            with tempfile.NamedTemporaryFile("w+") as tmp:
                with open(filepath, "r", encoding="utf-8") as fp:
                    tmp.file.write(fp.read())
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
            except SyntaxError as e:
                exc = e

        _logger.error(f"Not parsable {filepath}: {exc}")
        raise exc

    def _parse_class_def(self, obj: ast.ClassDef, content: str) -> None:
        model = Model.from_ast(obj, content)
        if not model.is_model():
            self.classes[model.name] = model
            return

        if model.name in self.models:
            self.models[model.name].update(model)
        else:
            self.models[model.name] = model

    def _parse_python(self, path, filename):
        if path + filename in self.files:
            return

        obj = self._load_python(path, filename)

        with open(os.path.join(path, filename), encoding="utf-8") as fp:
            content = fp.read()

        self.add(files=os.path.join(path, filename))

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
                if os.path.isfile(os.path.join(p, f"{f}.py")):
                    self._parse_python(p, f"{f}.py")
                    continue

                subdir = os.path.join(p, f)
                if os.path.isfile(os.path.join(subdir, "__init__.py")):
                    self._parse_python(subdir, "__init__.py")
                elif os.path.isdir(subdir):
                    p = subdir
                else:
                    break

    def _parse_manifest(self, path):
        with open(path, encoding="utf-8") as fp:
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

    def _parse_js(self, path, pattern):
        """Parse JavaScript files.
        `path` .. directory of the module
        `pattern` .. relative path/glob of the JS files"""

        for file in glob.glob(os.path.join(path, pattern.strip("/")), recursive=True):
            if not file.endswith(".js"):
                continue

            module = JSModule.from_file(file, pattern)
            if not module:
                return

            self.js_modules[module.name] = module

    def _parse_assets(self, parent_path):
        for files in self.manifest.get("assets", {}).values():
            for file in files:
                # Might be a tuple with include/remove
                if not isinstance(file, str) and file[0] == "remove":
                    continue
                if not isinstance(file, str):
                    file = file[-1]

                self._parse_js(parent_path, file)

    def _parse_xml(self, path, parent_path=None):
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

        # xpaths to get all referred modules
        xpaths = [
            "//record/field[@name='inherit_id']/@ref",
            "//template/@inherit_id",
            "//record[@model='ir.ui.view']/field[@name='arch']//@t-call",
            "//template//@t-call",
        ]
        xpaths.extend(f"//{tag}/@id" for tag in tags)

        xmlid = re.compile(r"\w+\.\w+")
        xpaths = " | ".join(xpaths)
        refs = {x.split(".")[0] for x in obj.xpath(xpaths) if xmlid.match(x)}
        self.refers.update({x for x in refs if x != self.name})

        # xpaths to extract views
        for node in obj.xpath("//record | //template"):
            rec = Record.from_xml(self.name, node)
            if not rec:
                continue

            if not rec.is_view():
                if rec.name in self.records:
                    self.records[rec.name].update(rec)
                else:
                    self.records[rec.name] = rec

            elif rec.name in self.views:
                self.views[rec.name].update(rec)
            else:
                self.views[rec.name] = rec

            for script in obj.xpath("//script/@src"):
                # this will return string a path,
                self._parse_js(parent_path, script)

    def _parse_text_for_keywords(self, texts):
        if not isinstance(texts, list):
            texts = [texts]

        words = stopwords()
        for text in texts:
            tmp = {w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", text)}
            self.words |= tmp.difference(words)

    def _parse_readme(self, path):
        with open(path, encoding="utf-8") as fp:
            self._parse_text_for_keywords(fp.read())

    def to_json(self):
        return {
            "path": self.path,
            "name": self.name,
            "duration": self.duration,
            "manifest": self.manifest,
            "models": {n: m.to_json() for n, m in self.models.items()},
            "classes": {n: c.to_json() for n, c in self.classes.items()},
            "js_modules": {n: m.to_json() for n, m in self.js_modules.items()},
            "views": {n: v.to_json() for n, v in self.views.items()},
            "records": {n: d.to_json() for n, d in self.records.items()},
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
        module.views = {n: Record.from_json(m) for n, m in data["views"].items()}
        module.js_modules = {
            n: JSModule.from_json(m) for n, m in data.get("js_modules", {}).items()
        }
        module.depends = set(data["depends"])
        module.imports = set(data["imports"])
        module.refers = set(data["refers"])
        module.files = set(data["files"])
        module.status = set(data["status"])
        module.language = data["language"]
        module.words = set(data["words"])
        module.hashsum = data["hashsum"]
        module.duration = data.get("duration") or 0

        records = data.get("records", {})
        module.records = {n: Record.from_json(d) for n, d in records.items()}

        classes = data.get("classes", {})
        module.classes = {n: Model.from_json(m) for n, m in classes.items()}

        return module

    @classmethod
    def from_path(cls, path):
        parent_path = str(Path(path).parent.absolute())
        files_list = []
        analyse_start = time.time()
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

        module._parse_assets(parent_path)

        for file in module.files:
            file_path = os.path.join(path, file)
            files_list.append(file_path)
            if file.endswith(".xml"):
                module._parse_xml(file_path, parent_path)
            elif file.endswith(".csv"):
                module._parse_csv(file_path)

        module.analyse_hash(files_list)

        _logger.info("Found module %s", module.name)
        if module.status:
            _logger.info("Status %s: %s", module.name, module.status)

        module.duration = time.time() - analyse_start
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
