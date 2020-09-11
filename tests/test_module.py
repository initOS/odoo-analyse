# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import os
from unittest import mock

from odoo_analyse import Model, Module, View, module


def get_module():
    modules = Module.find_modules(os.path.abspath("tests/"))
    return modules["testing_module"]


def test_module():
    mod = get_module()

    assert repr(mod) == "<Module: testing_module>"

    # Check the manifest
    assert mod.author == "initOS GmbH"
    assert mod.category == "Hidden"
    assert mod.description == "description"
    assert mod.external_dependencies == {}
    assert mod.installable
    assert mod.license == "license"
    assert mod.summary == "summary"
    assert mod.version == "x.0.1.0.0"
    assert mod.website == "https://example.org"
    assert mod.info.get("model_count") == 3

    assert "base" in mod.depends


def test_module_json():
    mod = get_module()

    json = mod.to_json()
    copied = Module.from_json(json).to_json()
    for key in set(copied).union(json):
        a, b = copied.get(key), json.get(key)
        if isinstance(a, list):
            a.sort()
        if isinstance(b, list):
            b.sort()
        assert a == b


def test_module_readme():
    mod = get_module()
    assert mod.readme
    assert mod.readme_type == ".md"

    module.is_readme = lambda x: False
    assert not mod.readme
    assert not mod.readme_type


def test_module_add():
    mod = get_module()

    assert "testing" not in mod.depends
    assert "testing" not in mod.imports
    assert "testing" not in mod.refers

    mod.add(depends="testing", imports="testing", refers="testing")

    assert "testing" in mod.depends
    assert "testing" in mod.imports
    assert "testing" in mod.refers


def test_model():
    mod = get_module()

    # Check the model
    model = mod.models["test.model"]
    json = model.to_json()
    copied = model.copy()

    assert repr(model) == "<Model: test.model>"
    assert copied != model
    assert copied.to_json() == json
    assert Model.from_json(json).to_json() == json


def test_view():
    mod = get_module()

    view = mod.views["testing_module.view_test_model"]
    json = view.to_json()
    copied = view.copy()

    assert repr(view) == "<View: testing_module.view_test_model>"
    assert copied != view
    assert copied.to_json() == json
    assert View.from_json(json).to_json() == json


def test_view_failing_functions():
    assert View.enforce_fullname(12, "testing_module") is None

    m = mock.MagicMock()
    m.tag = "record"
    assert View.from_xml("testing_module", m) is None
