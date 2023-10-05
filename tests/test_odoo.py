import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from odoo_analyse import Odoo
from odoo_analyse import odoo as o


@pytest.fixture
def odoo():
    return Odoo.from_path(os.path.abspath("tests"))


def check_odoo(odoo):
    assert len(odoo) == 1
    assert "testing_module" in odoo
    assert list(odoo)
    assert isinstance(odoo.items(), type(odoo.modules.items()))
    assert odoo["testing_module"]


def test_odoo_path(odoo):
    check_odoo(odoo)

    odoo.modules["test"] = odoo["testing_module"]

    assert odoo.models()
    assert odoo.views()

    # Check the dependency generation
    assert not odoo._full_dependency("unknown")
    odoo._full_dependency("testing_module")


def test_odoo_creation():
    path = os.path.abspath("tests")
    assert Odoo.from_path("%s/testing_module/__manifest__.py" % path) is None

    with tempfile.NamedTemporaryFile("w+") as cfg:
        cfg.write("[options]\naddons_path=%s\n" % path)
        cfg.seek(0)

        check_odoo(Odoo.from_config(cfg.name))


def test_odoo_config():
    odoo = Odoo()

    with tempfile.NamedTemporaryFile("w+") as cfg:
        cfg.write("[a]\nb=100\n")
        cfg.seek(0)

        odoo.load_config(cfg.name)
        assert odoo.opt("a.b") == "100"
        assert odoo.opt("a.c") is None
        assert odoo.opt("a.c", 42) == 42

        odoo.set_opt("a.c", True)
        assert odoo.opt("a.c") is True


def test_odoo_analyse(odoo):
    odoo.analyse("-")
    odoo.analyse("-", out_format="csv")


def test_odoo_json(odoo):
    with tempfile.NamedTemporaryFile("w+") as json:
        odoo.save_json(json.name)

        odoo.load_json(json.name)
        assert len(odoo)


def test_odoo_filters(odoo):
    odoo = Odoo.from_path(os.path.abspath("tests"))

    module = odoo["testing_module"]

    # Test the test_ filter
    odoo.modules["test_"] = module
    odoo.test_filter()
    assert len(odoo) == 1

    # Test the name filter
    odoo.modules["abc"] = module
    odoo.name_filter("a*c")
    assert len(odoo) == 1

    odoo.path_filter("testing/*")
    assert not odoo

    db = MagicMock()
    with patch("odoo_analyse.odoo.connect", return_value=db) as mock:
        odoo.modules["abc"] = odoo.modules["def"] = module
        cr = db.__enter__.return_value = MagicMock()
        cur = cr.cursor.return_value = MagicMock()
        cur.fetchall.return_value = [("def", "installed")]
        odoo.load_state_from_database()

        mock.assert_called_once()
        cr.cursor.assert_called_once()

        cur.execute.assert_called_once()
        odoo.state_filter()


def test_odoo_run_graph(odoo):
    o.Graph = o.Digraph = MagicMock()
    odoo.set_opt("odoo.show_full_dependency", True)
    odoo.show_structure_graph()
    odoo.show_module_graph()
    odoo.show_model_graph()
    odoo.show_view_graph()
