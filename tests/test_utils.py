import os
import shutil
from tempfile import NamedTemporaryFile
from unittest import mock

from odoo_analyse import utils


def test_blacklist():
    assert not utils.folder_blacklist()
    folders = ["hello", "world"]
    assert sorted(utils.folder_blacklist(folders)) == folders
    assert sorted(utils.folder_blacklist()) == folders


def test_call():
    path = "tests/files"
    output, error = utils.call("ls", cwd=path)
    assert set(output.splitlines()) == set(os.listdir(path))
    assert not error


def test_fix_indentation():
    def check(content, fixed):
        with NamedTemporaryFile("w+") as tmp:
            tmp.write(content)
            tmp.seek(0)
            if content == fixed:
                assert not utils.fix_indentation(tmp.name)
            else:
                assert utils.fix_indentation(tmp.name)
            tmp.seek(0)
            assert tmp.read().rstrip() == fixed

    check("Hello World", "Hello World")
    check(" Hello World", " Hello World")
    check("    Hello World", "    Hello World")
    check("\tHello World", "    Hello World")
    check(" \tHello World", "    Hello World")


def test_hashhex():
    result = "5eb63bbbe01eeed093cb22bb8f5acdc3"
    assert utils.hexhash("hello world") == result
    assert utils.hexhash(b"hello world") == result


def test_hashhex_files():
    base = "tests/files"
    file_a = "%s/a.txt" % base
    file_b = "%s/b.txt" % base
    result_a = "9db6c23f9bd47910c1ed8c002acf2af0"
    result_b = "cd5684de227a381e0f81d23eec4aa8ae"
    result = "397578ed65a6340fcf864594306b4198"

    assert utils.hexhash_files([file_a], base) == result_a
    assert utils.hexhash_files([file_b], base) == result_b
    assert utils.hexhash_files([file_b, file_b], base) == result_b
    assert utils.hexhash_files([file_a, file_b], base) == result
    assert utils.hexhash_files([file_b, file_a], base) == result


def test_stopwords():
    assert not utils.stopwords()
    words = ["hello", "world"]
    assert sorted(utils.stopwords(words)) == words
    assert sorted(utils.stopwords()) == words


def test_analyse_language():
    data = utils.analyse_language("tests/testing_module")
    assert data["Markdown"]["lines"] == 3

    # Missing module
    assert not utils.analyse_language("tests/no_module")


def test_automatic_port():
    with NamedTemporaryFile("w+") as f:
        f.write("print 'Hello World'\n")
        f.seek(0)

        assert utils.try_automatic_port(f.name)
        assert f.read() == "print('Hello World')\n"


def test_missing_tools():
    # Not installed cloc
    orig = shutil.which
    m = shutil.which = mock.MagicMock()
    m.return_value = None

    try:
        res_analyse = utils.analyse_language("file")
        res_port = utils.try_automatic_port("file")
    finally:
        shutil.which = orig

    assert m.call_count == 2
    assert res_analyse == {}
    assert res_port is False
