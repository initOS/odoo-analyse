# © 2019 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import ast
import hashlib
import json
import logging
import os
import shutil
import subprocess
from functools import reduce
from json.decoder import JSONDecodeError

_logger = logging.getLogger(__name__)


def call(cmd, cwd=None):
    with subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=cwd,
        universal_newlines=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    ) as proc:
        return [pipe.strip() for pipe in proc.communicate()]


def stopwords(words=None):
    """Returns or stores the stopword set"""
    if words:
        stopwords.words = words
        return words
    if hasattr(stopwords, "words"):
        return stopwords.words
    return set()


def folder_blacklist(blacklist=None):
    """Returns or stores the folder blacklist"""
    if blacklist:
        folder_blacklist.blacklist = blacklist
        return blacklist
    if hasattr(folder_blacklist, "blacklist"):
        return folder_blacklist.blacklist
    return set()


def hexhash(s):
    """Generates a hash and returns it as hex"""
    if not isinstance(s, bytes):
        s = s.encode()
    return hashlib.md5(s).hexdigest()


def hexhash_files(files, folder):
    """Generates a hash for a list of files"""
    hashes = []
    for f in sorted(set(files)):
        if os.path.isfile(f):
            with open(f, "rb") as fp:
                hashsum = hexhash(fp.read())
        else:
            hashsum = "-"

        rel_path = os.path.relpath(f, folder) if f.startswith(folder) else f
        hashes.append(f"{hashsum} {rel_path}")
    return hexhash("\n".join(hashes))


def fix_indentation(filepath):
    """Fixes the indentation of a file"""
    result = False
    with open(filepath, "r+", encoding="utf-8") as fp:
        buf = fp.read()

    with open(filepath, "w+", encoding="utf-8") as fp:
        for line in buf.splitlines():
            left = ""
            for c in line:
                if c == " ":
                    left += c
                elif c == "\t":
                    left += " " * (4 - len(left) % 4)
                    result = True
                else:
                    break
            fp.write(f"{left}{line.strip()}\n")

    return result


def try_automatic_port(filepath):
    """Tries to port a python 2 script to python 3 using 2to3"""
    cmd = shutil.which("2to3")
    if cmd is None:
        _logger.warning("Automatic porting needs 2to3 installed")
        return False

    with subprocess.Popen(
        [cmd, "-n", "-w", filepath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:
        proc.communicate()
    return True


def analyse_language(path):
    """Analyse the languages of a directory"""
    cmd = shutil.which("cloc")
    if cmd is None:
        _logger.warning("Language analyse needs cloc")
        return {}

    output, error = call([cmd, path, "--json"])
    if error:
        _logger.warning(error)

    try:
        output = json.loads(output)
    except ValueError as err:
        _logger.warning(err)
        return {}

    total_code = 0
    result = {}
    for key, val in output.items():
        if "code" not in val:
            # skipping 'header' and anyother non-lang keys
            continue

        code = int(val["code"])
        total_code += code
        result[key] = {"lines": code, "fraction_from_total": 0}

    for value in result.values():
        value["fraction_from_total"] = value["lines"] / total_code

    return result


def get_ast_source_segment(source, node):
    # Adapted from https://github.com/python/cpython/blob/3.8/Lib/ast.py
    try:
        start = node.lineno - 1
        end = node.end_lineno - 1
        start_offset = node.col_offset
        end_offset = node.end_col_offset
    except AttributeError:
        return None

    lines = ast._splitlines_no_ff(source)
    if end == start:
        return lines[start].encode()[start_offset:end_offset].decode()

    segment = [lines[start].encode()[start_offset:].decode()]
    segment.extend(lines[start + 1 : end])
    segment.append(lines[end].encode()[:end_offset].decode())
    return "".join(segment)


def eslint_complexity(js_file):
    """Return the JS complexity using eslintcc"""
    cmd = shutil.which("eslintcc")
    if not cmd:
        _logger.warning(f"eslintcc not found. Skipping complexity for js {js_file}")
        return None

    output, _ = call([cmd, "-a", "-f=json", js_file])
    try:
        output = json.loads(output)
    except JSONDecodeError:
        return None
    return output["average"]["rank"]


def geometric_mean(data):
    data = list(filter(None, data))
    if not data:
        return 0

    return pow(reduce(lambda x, y: x * y, data), 1 / len(data))
