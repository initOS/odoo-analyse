
from tempfile import NamedTemporaryFile

from odoo_analyse import utils


def test_blacklist():
    assert not utils.folder_blacklist()
    folders = ["hello", "world"]
    assert sorted(utils.folder_blacklist(folders)) == folders
    assert sorted(utils.folder_blacklist()) == folders


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
    result_a = "29bcbed04e4a826937d6d61ea0865be2"
    result_b = "a8dfc1610c2ac8b0af0cdd2736e69a98"
    result = "98cc886094f719b556d563f067ed79e9"
    assert utils.hexhash_files(["files/a.txt"]) == result_a
    assert utils.hexhash_files(["files/b.txt"]) == result_b
    assert utils.hexhash_files(["files/b.txt", "files/b.txt"]) == result_b
    assert utils.hexhash_files(["files/a.txt", "files/b.txt"]) == result
    assert utils.hexhash_files(["files/b.txt", "files/a.txt"]) == result


def test_stopwords():
    assert not utils.stopwords()
    words = ["hello", "world"]
    assert sorted(utils.stopwords(words)) == words
    assert sorted(utils.stopwords()) == words
