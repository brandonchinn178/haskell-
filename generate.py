#!/usr/bin/env python3

"""
Generate the Haskell syntax definition file.

Sublime Text currently doesn't make it possible to use backreferences
to reference captures beyond a context's immediate parent. To get
around that, we'll just generate a syntax file with every possible
indentation hardcoded.

https://forum.sublimetext.com/t/syntax-definition-explicitly-specify-backref-context/60899
"""

import yaml
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "Haskell-Syntax.template.sublime-syntax"
OUTPUT = HERE / "Haskell-Syntax.sublime-syntax"

MAX_INDENTATION = 40

def main():
    data = yaml.load(TEMPLATE.read_text(), Loader=yaml.Loader)

    # TODO

    out = yaml.dump(data, Dumper=yaml.Dumper)
    OUTPUT.write_text("%YAML 1.2\n---\n" + out)

if __name__ == '__main__':
    main()
