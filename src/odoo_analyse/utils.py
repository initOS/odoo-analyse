# © 2019 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import hashlib
import logging
import os
import re
import shutil
import subprocess

_logger = logging.getLogger(__name__)


def call(cmd, cwd=None):
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=cwd,
        universal_newlines=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return [pipe.strip() for pipe in proc.communicate()]


def stopwords(words=None):
    """ Returns or stores the stopword set """
    if words:
        stopwords.words = words
        return words
    if hasattr(stopwords, "words"):
        return stopwords.words
    return set()


def folder_blacklist(blacklist=None):
    """ Returns or stores the folder blacklist """
    if blacklist:
        folder_blacklist.blacklist = blacklist
        return blacklist
    if hasattr(folder_blacklist, "blacklist"):
        return folder_blacklist.blacklist
    return set()


def hexhash(s):
    """ Generates a hash and returns it as hex """
    if not isinstance(s, bytes):
        s = s.encode()
    return hashlib.md5(s).hexdigest()


def hexhash_files(files, folder):
    """ Generates a hash for a list of files """
    hashes = []
    for f in sorted(set(files)):
        if os.path.isfile(f):
            hashsum = hexhash(open(f, "rb").read())
        else:
            hashsum = "-"

        rel_path = os.path.relpath(f, folder) if f.startswith(folder) else f
        hashes.append(f"{hashsum} {rel_path}")
    return hexhash("\n".join(hashes))


def fix_indentation(filepath):
    """ Fixes the indentation of a file """
    result = False
    with open(filepath, "r+") as fp:
        buf = fp.read()

    with open(filepath, "w+") as fp:
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
    """ Tries to port a python 2 script to python 3 using 2to3 """
    cmd = shutil.which("2to3")
    if cmd is None:
        _logger.warning("Automatic porting needs 2to3 installed")
        return False

    proc = subprocess.Popen(
        [cmd, "-n", "-w", filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    proc.communicate()
    return True


def analyse_language(path):
    """ Analyse the languages of a directory """
    cmd = shutil.which("cloc")
    if cmd is None:
        _logger.warning("Language analyse needs cloc")
        return {}

    output, error = call([cmd, path])
    if error:
        return {}

    result = {}
    reg = re.compile(r"([^:]*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")
    total_code = 0
    for line in output.splitlines():
        match = reg.match(line)
        if match:
            lang, _, _, _, code = match.groups()
            total_code += int(code)
            result[lang] = {"lines": int(code), "fraction_from_total": 0}

    for value in result.values():
        value["fraction_from_total"] = value["lines"] / total_code

    return result
