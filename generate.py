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
from typing import Any, Callable

HERE = Path(__file__).parent
TEMPLATE = HERE / "Haskell-Syntax.template.sublime-syntax"
OUTPUT = HERE / "Haskell-Syntax.sublime-syntax"

MAX_INDENTATION = 40
INDENTATIONS = list(range(0, MAX_INDENTATION + 1))[::-1]

INDENTATION_MARKER = "{{INDENTATION}}"

def main():
    # read in old data
    data = decode_yaml(TEMPLATE.read_text())
    old_contexts = data["contexts"]

    # find all indented contexts
    indented_contexts = get_indented_contexts(old_contexts)

    # find all branch points within duplicated context
    branch_points_to_duplicate = set()
    for context in indented_contexts:
        for pattern in old_contexts[context]:
            branch_point = pattern.get("branch_point")
            if branch_point:
                branch_points_to_duplicate.add(branch_point)

    new_contexts = {}
    def _add_new_context(context_name, indent, patterns):
        if indent is not None:
            context_name = name_with_indent(context_name, indent)
        new_contexts[context_name] = patterns

    for context, patterns in old_contexts.items():
        # duplicate "pop_when_deindent" manually
        if context == "pop_when_deindent":
            for i in INDENTATIONS:
                _add_new_context(context, i, [
                    {
                        "match": r"^(?!%s\s)" % indent_regex(i),
                        "pop": True,
                    },
                ])
            continue

        indentations = INDENTATIONS if context in indented_contexts else [None]
        for indent in indentations:
            new_patterns = []

            def _pattern_with_indent(pattern, indent):
                if indent is None:
                    return pattern

                new_pattern = pattern_with_indent(pattern, indent)

                # TODO(nested-indent): generalize this to set indentation of branch_point
                # to the appropriate indentation, instead of the current indentation
                branch_point = new_pattern.get("branch_point")
                if branch_point and branch_point in branch_points_to_duplicate:
                    new_pattern["branch_point"] = name_with_indent(branch_point, indent)

                branch_fail = new_pattern.get("fail")
                if branch_fail and branch_fail in branch_points_to_duplicate:
                    new_pattern["fail"] = name_with_indent(branch_fail, indent)

                return new_pattern

            for pattern in patterns:
                pattern_match = pattern.get("match", "")
                if INDENTATION_MARKER in pattern_match:
                    # TODO(nested-indent): handle when `indent is not None`
                    for indent_inner in INDENTATIONS:
                        new_pattern = _pattern_with_indent(pattern, indent_inner)
                        new_pattern["match"] = pattern_match.replace(
                            INDENTATION_MARKER,
                            # special case; '\s{0}' doesn't seem to work here
                            r"(?!\s)" if indent_inner == 0 else indent_regex(indent_inner),
                        )
                        new_patterns.append(new_pattern)
                else:
                    new_pattern = _pattern_with_indent(pattern, indent)
                    new_patterns.append(new_pattern)

            _add_new_context(context, indent, new_patterns)

    # write out new data
    data["contexts"] = new_contexts
    OUTPUT.write_text(encode_yaml(data))

### Indentation strings ###

def name_with_indent(name: str, indent: int) -> str:
    # TODO(extraneous): remove this manual workaround
    if name in (
        "data_type_record",
        "expression",
        "function",
        "import_list",
        "module_header_line",
        "pattern_match",
        "pattern_match_record",
        "type",
    ):
        return name

    return f"{name}__{indent}"

def indent_regex(indent: int) -> str:
    return r"\s{%d}" % indent

### Finding indented contexts ###

Pattern = dict
Patterns = list[Pattern]
ContextName = str

def get_indented_contexts(contexts: dict[ContextName, Patterns]) -> set[ContextName]:
    indented_contexts = set()

    context_queue = [("main", None), ("prototype", None)]
    seen = set()
    while len(context_queue) > 0:
        context, path = context_queue.pop(0)

        if context in indented_contexts:
            indented_contexts.update(path or [])
            continue

        # check cycles
        node = (context, None if path is None else tuple(path))
        if (node in seen) or (path and context in path):
            continue
        seen.add(node)

        path = None if path is None else path + [context]
        for pattern in contexts[context]:
            if pattern.get("include") == "pop_when_deindent":
                indented_contexts.update(path or [])

            # TODO(nested-indent): when matching indentation within indented context,
            # nest indentation indicators; e.g. `function_signature_start__2__4`, so
            # that we can use 'function__2' as a branch point
            if INDENTATION_MARKER in pattern.get("match", "") and path is None:
                next_path = []
            else:
                next_path = path

            context_queue.extend(
                (next_context, next_path)
                for next_context in get_contexts_in_pattern(pattern)
            )

    return indented_contexts

def get_contexts_in_pattern(pattern: Pattern) -> list[ContextName]:
    contexts = []

    transform_pattern(
        pattern,
        on_subcontext=contexts.append,
    )

    return contexts

### Pattern ###

# TODO(extraneous): fix when this context is duplicated but pushed context isn't
def pattern_with_indent(pattern: dict, indent: int) -> dict:
    return transform_pattern(
        pattern,
        on_subcontext=lambda context: name_with_indent(context, indent),
    )

def transform_pattern(
    pattern: Pattern,
    *,
    on_subcontext: Callable[[ContextName], Any],
) -> dict:
    new_pattern = {}

    pattern_include = pattern.get("include")
    if pattern_include:
        new_pattern["include"] = on_subcontext(pattern_include)

    pattern_match = pattern.get("match")
    if pattern_match:
        pattern_embed = pattern.get("embed")
        if pattern_embed:
            new_pattern["embed"] = on_subcontext(pattern_embed)

        pattern_branches = pattern.get("branch")
        if pattern_branches:
            new_pattern["branch"] = [
                on_subcontext(pattern_branch)
                for pattern_branch in pattern_branches
            ]

        for key in ["push", "set"]:
            pattern_next = pattern.get(key)
            if pattern_next is None:
                continue
            if isinstance(pattern_next, str):
                new_pattern[key] = on_subcontext(pattern_next)
            elif all(isinstance(p, str) for p in pattern_next):
                new_pattern[key] = [
                    on_subcontext(p)
                    for p in pattern_next
                ]
            else:
                new_pattern[key] = [
                    transform_pattern(p, on_subcontext=on_subcontext)
                    for p in pattern_next
                ]

    return { **pattern, **new_pattern }

### YAML ###

def decode_yaml(s):
    return yaml.load(s, Loader=yaml.Loader)

def encode_yaml(data):
    Dumper = yaml.Dumper
    Dumper.ignore_aliases = lambda self, data: True
    return "%YAML 1.2\n---\n" + yaml.dump(data, Dumper=Dumper)

### Entrypoint ###

if __name__ == "__main__":
    main()
