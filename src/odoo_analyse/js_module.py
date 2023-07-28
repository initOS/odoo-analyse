import logging
import os
import re

from .utils import eslint_complexity

# Adapted from odoo.tools.js_transpiler
ODOO_MODULE_RE = re.compile(
    r"""
    \s*                                       # some starting space
    \/(\*|\/).*\s*                            # // or /*
    @odoo-module                              # @odoo-module
    (\s+alias=(?P<alias>[\w.]+))?             # alias=web.AbstractAction (optional)
    (\s+default=(?P<default>False|false|0))?  # default=False or false or 0 (optional)
""",
    re.VERBOSE,
)


REQUIRE_RE = re.compile(
    r"""require\s*\(\s*(?P<quote>["'`])(?P<path>[^"'`]*?)(?P=quote)\s*\)""",
    re.MULTILINE | re.VERBOSE,
)


ODOO_DEFINE_RE = re.compile(
    r"""odoo\s*\.\s*define\s*\(\s*(?P<quote>["'`])(?P<path>[^"'`]*?)(?P=quote)""",
    re.MULTILINE | re.VERBOSE,
)


IMPORT_BASIC_RE = re.compile(
    r"""
    ^
    \s*import\s+                           # import
    (?P<object>{(\s*\w+\s*,?\s*)+})\s*  # { a, b, c as x, ... }
    from\s*                             # from
    (?P<quote>["'`])(?P<path>[^"'`]+)(?P=quote)   # "file path" ("some/path")
""",
    re.MULTILINE | re.VERBOSE,
)

URL_RE = re.compile(
    r"""
    /?(?P<module>\S+)    # /module name
    /([\S/]*/)?static/   # ... /static/
    (?P<type>src|tests)  # src or test file
    (?P<url>/[\S/]*)     # URL (/...)
    """,
    re.VERBOSE,
)


def url_to_module_path(url):
    """
    Odoo modules each have a name. (odoo.define("<the name>", function (require) {...});
    It is used in to be required later. (const { something } = require("<the name>").
    The transpiler transforms the url of the file in the project to this name.
    It takes the module name and add a @ on the start of it, and map it to be the source
    of the static/src (or static/tests) folder in that module.

    in: web/static/src/one/two/three.js
    out: @web/one/two/three.js
    The module would therefore be defined and required by this path.

    :param url: an url in the project
    :return: a special path starting with @<module-name>.
    """
    match = URL_RE.match(url)
    if match:
        url = match["url"]
        if url.endswith(("/index.js", "/index")):
            url, _ = url.rsplit("/", 1)
        if url.endswith(".js"):
            url = url[:-3]
        if match["type"] == "src":
            return "@%s%s" % (match["module"], url)

        return "@%s/../tests%s" % (match["module"], url)
    return url


_logger = logging.getLogger(__name__)


class JSModule:
    def __init__(self, name, alias=None, complexity=None, default=True, requires=None):
        self.name = name
        self.alias = alias or None
        self.default = bool(default)
        self.requires = set(requires or [])
        self.complexity = complexity or 0

    def __repr__(self):
        name = self.name
        if self.alias:
            name = "%s/%s" % (name, self.alias)
        return "<JS: %s>" % name

    def copy(self):
        return JSModule(
            self.name,
            self.alias,
            self.complexity,
            self.default,
            self.requires,
        )

    def to_json(self):
        return {
            "name": self.name,
            "alias": self.alias,
            "complexity": self.complexity,
            "default": self.default,
            "requires": list(self.requires),
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            data["name"],
            alias=data.get("alias", None),
            complexity=data.get("complexity", None),
            default=data.get("default", True),
            requires=data.get("requires", None),
        )

    @classmethod
    def from_file(cls, path, file):
        if not os.path.isfile(path):
            return None

        with open(path, encoding="utf-8") as fp:
            content = fp.read()

        name = url_to_module_path(file)

        complexity = eslint_complexity(path)

        # Old odoo.define format
        defines = ODOO_DEFINE_RE.findall(content)
        if defines:
            if len(defines) > 1:
                _logger.warning("Multiple odoo.define in single JS %s", name)

            define = defines[0][1]
            requires = [x[1] for x in REQUIRE_RE.findall(content)]
            return cls(name, alias=define, complexity=complexity, requires=requires)

        # Newer odoo-module format
        module = ODOO_MODULE_RE.findall(content)
        if module:
            imports = [x[-1] for x in IMPORT_BASIC_RE.findall(content)]
            requires = [x[1] for x in REQUIRE_RE.findall(content)]
            return cls(
                name,
                alias=module[0][2],
                complexity=complexity,
                default=not module[0][4],
                requires=imports + requires,
            )

        return cls(name, complexity=complexity)
