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
INDENTATIONS = list(range(0, MAX_INDENTATION + 1))[::-1]

INDENTATION_MARKER = "{{INDENTATION}}"

def main():
    data = yaml.load(TEMPLATE.read_text(), Loader=yaml.Loader)

    new_contexts = {}

    # copy prototype + main separately
    new_contexts["main"] = duplicate_all_patterns(data["contexts"]["main"], 0)
    new_contexts["prototype"] = duplicate_all_patterns(data["contexts"]["prototype"], 0)

    # duplicate "pop_when_deindent" separately
    for i in INDENTATIONS:
        new_contexts[name_with_indent("pop_when_deindent", i)] = [
            {
                "match": r"^(?!%s\s)" % indent_regex(i),
                "pop": True,
            },
        ]

    # For every other context:
    #   * Duplicate it for all indentations
    #   * If the context has a pattern with a 'match: ^(INDENTATION)...'
    #     field, duplicate that pattern for each indentation and update
    #     all contexts referenced in that pattern to reference the same
    #     indentation as the pattern
    #   * All other contexts referenced within this context should
    #     reference the same indentation as this context
    for name, patterns in data["contexts"].items():
        if name in {"main", "prototype", "pop_when_deindent"}:
            continue

        for i in INDENTATIONS:
            new_contexts[name_with_indent(name, i)] = duplicate_all_patterns(patterns, i)

    data["contexts"] = new_contexts

    Dumper = yaml.Dumper
    Dumper.ignore_aliases = lambda self, data: True
    out = yaml.dump(data, Dumper=Dumper)

    OUTPUT.write_text("%YAML 1.2\n---\n" + out)

def duplicate_all_patterns(patterns: list[dict], indent: int):
    return [
        p
        for pattern in patterns
        for p in duplicate_pattern(pattern, indent)
    ]

def duplicate_pattern(pattern: dict, indent: int) -> list[dict]:
    pattern_include = pattern.get("include")
    if pattern_include:
        assert len(pattern) == 1, "include pattern had more than one field"
        return [
            { "include": name_with_indent(pattern_include, indent) }
        ]

    pattern_match = pattern.get("match")
    if pattern_match:
        indentations = INDENTATIONS if INDENTATION_MARKER in pattern_match else [indent]
        new_patterns = []

        for i in indentations:
            new_pattern = pattern.copy()
            new_pattern["match"] = pattern_match.replace(
                INDENTATION_MARKER,
                # special case (i=0); '\s{0}' doesn't seem to work here
                r"(?!\s)" if i == 0 else indent_regex(i)
            )

            pattern_embed = pattern.get("embed")
            if pattern_embed:
                new_pattern["embed"] = name_with_indent(pattern_embed, i)

            pattern_branch = pattern.get("branch")
            if pattern_branch:
                new_pattern["branch"] = [
                    name_with_indent(branch, i)
                    for branch in pattern_branch
                ]
                new_pattern["branch_point"] = name_with_indent(pattern["branch_point"], i)

            pattern_push = pattern.get("push")
            pattern_set = pattern.get("set")
            if pattern_push or pattern_set:
                key, item = ("push", pattern_push) if pattern_push else ("set", pattern_set)

                if isinstance(item, str):
                    new_pattern[key] = name_with_indent(item, i)
                elif all(isinstance(p, str) for p in item):
                    new_pattern[key] = [
                        name_with_indent(p, i)
                        for p in item
                    ]
                else:
                    new_pattern[key] = duplicate_all_patterns(item, i)

            pattern_fail = pattern.get("fail")
            if pattern_fail:
                new_pattern["fail"] = name_with_indent(pattern_fail, i)

            new_patterns.append(new_pattern)

        return new_patterns

    return [pattern]

def name_with_indent(name: str, indent: int) -> str:
    return f"{name}__{indent}"

def indent_regex(indent: int) -> str:
    return r"\s{%d}" % indent

if __name__ == "__main__":
    main()
