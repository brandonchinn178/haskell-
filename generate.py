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
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = HERE / "Haskell-Syntax.template.sublime-syntax"
OUTPUT = HERE / "Haskell-Syntax.sublime-syntax"

MAX_INDENTATION = 40
INDENTATIONS = list(range(0, MAX_INDENTATION + 1))[::-1]

INDENTATION_MARKER = "{{INDENTATION}}"

def main():
    # read in old data
    data = decode_yaml(TEMPLATE.read_text())
    contexts = ContextRegistry.parse(data)

    new_contexts = {}
    copied_contexts = set()
    def _add_new_context(name, patterns, indent=None):
        new_name = name_with_indent(name, indent) if indent is not None else name
        new_contexts[new_name] = patterns
        copied_contexts.add(name)

    # duplicate all indentation-introducing match patterns
    indent_introducing_patterns = []
    for context in contexts.all_contexts:
        if not context.starts_indent:
            continue

        new_patterns = []
        for pattern in context.patterns:
            pattern_match = pattern.get("match", "")

            if INDENTATION_MARKER not in pattern_match:
                new_patterns.append(pattern)
                continue

            new_patterns.extend(
                {
                    **pattern_with_indent(pattern, i),
                    "match": pattern_match.replace(
                        INDENTATION_MARKER,
                        # special case (i=0); '\s{0}' doesn't seem to work here
                        r"(?!\s)" if i == 0 else indent_regex(i),
                    ),
                }
                for i in INDENTATIONS
            )
            indent_introducing_patterns.append(pattern)

        _add_new_context(context.name, new_patterns)

    # find all contexts to duplicate
    contexts_to_duplicate = set()
    seen = set()
    queue = [
        (context, [])
        for pattern in indent_introducing_patterns
        for context in contexts_in_pattern(pattern)
    ]
    while len(queue) > 0:
        context_name, path = queue.pop(0)
        if context_name in seen:
            continue

        seen.add(context_name)
        path.append(context_name)

        context = contexts.get_context(context_name)
        if context.ends_indent:
            contexts_to_duplicate.update(path)

        queue.extend(
            (c, path)
            for c in context.children
        )

    # find all branch points within duplicated context
    branch_points_to_duplicate = set()
    for context_name in contexts_to_duplicate:
        context = contexts.get_context(context_name)
        for pattern in context.patterns:
            branch_point = pattern.get("branch_point")
            if branch_point:
                branch_points_to_duplicate.add(branch_point)

    # duplicate "pop_when_deindent" manually
    for i in INDENTATIONS:
        _add_new_context(
            name="pop_when_deindent",
            patterns=[
                {
                    "match": r"^(?!%s\s)" % indent_regex(i),
                    "pop": True,
                },
            ],
            indent=i,
        )

    # duplicate all contexts between a context introducing indentation and a
    # context that pops indentation
    for context_name in contexts_to_duplicate:
        context = contexts.get_context(context_name)
        for i in INDENTATIONS:
            new_patterns = []
            for pattern in context.patterns:
                new_pattern = pattern_with_indent(pattern, i)

                branch_point = new_pattern.get("branch_point")
                if branch_point and branch_point in branch_points_to_duplicate:
                    new_pattern["branch_point"] = name_with_indent(branch_point, i)

                branch_fail = new_pattern.get("fail")
                if branch_fail and branch_fail in branch_points_to_duplicate:
                    new_pattern["fail"] = name_with_indent(branch_fail, i)

                new_patterns.append(new_pattern)

            _add_new_context(
                name=context_name,
                patterns=new_patterns,
                indent=i,
            )

    # copy everything else over
    for context in contexts.all_contexts:
        if context.name not in copied_contexts:
            _add_new_context(context.name, data["contexts"][context.name])

    # write out new data
    data["contexts"] = new_contexts
    OUTPUT.write_text(encode_yaml(data))

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

### Pattern ###

# TODO: visitor pattern?
def contexts_in_pattern(pattern: dict) -> set[str]:
    contexts = set()

    pattern_include = pattern.get("include")
    if pattern_include:
        contexts.add(pattern_include)

    pattern_match = pattern.get("match")
    if pattern_match:
        pattern_embed = pattern.get("embed")
        if pattern_embed:
            contexts.add(pattern_embed)

        pattern_branches = pattern.get("branch", [])
        contexts.update(pattern_branches)

        for key in ["push", "set"]:
            pattern_next = pattern.get(key)
            if pattern_next is None:
                continue
            if isinstance(pattern_next, str):
                contexts.add(pattern_next)
            elif all(isinstance(p, str) for p in pattern_next):
                contexts.update(pattern_next)
            else:
                contexts.update(
                    context
                    for p in pattern_next
                    for context in contexts_in_pattern(p)
                )

    return contexts


# TODO(extraneous): fix when this context is duplicated but pushed context isn't
def pattern_with_indent(pattern: dict, indent: int) -> dict:
    pattern_include = pattern.get("include")
    if pattern_include:
        return {
            "include": name_with_indent(pattern_include, indent),
        }

    pattern_match = pattern.get("match")
    if pattern_match:
        new_pattern = pattern.copy()

        pattern_embed = pattern.get("embed")
        if pattern_embed:
            new_pattern["embed"] = name_with_indent(pattern_embed, indent)

        pattern_branch = pattern.get("branch")
        if pattern_branch:
            new_pattern["branch"] = [
                name_with_indent(branch, indent)
                for branch in pattern_branch
            ]

        for key in ["push", "set"]:
            pattern_next = pattern.get(key)
            if not pattern_next:
                continue
            if isinstance(pattern_next, str):
                new_pattern[key] = name_with_indent(pattern_next, indent)
            elif all(isinstance(p, str) for p in pattern_next):
                new_pattern[key] = [
                    name_with_indent(p, indent)
                    for p in pattern_next
                ]
            else:
                new_pattern[key] = [
                    pattern_with_indent(p, indent)
                    for p in pattern_next
                ]

        # TODO(extraneous): fix when this context is duplicated but the branch point isn't
        pattern_fail = pattern.get("fail")
        if pattern_fail:
            new_pattern["fail"] = name_with_indent(pattern_fail, indent)

        return new_pattern

    return pattern

### Contexts ###

@dataclass
class ContextInfo:
    name: str
    starts_indent: bool  # has a pattern that matches on indentation level
    ends_indent: bool  # includes pop_when_deindent
    children: list[str]
    patterns: list

    @classmethod
    def parse(cls, name: str, patterns: list[dict]) -> "ContextInfo":
        context = cls(
            name=name,
            starts_indent=False,
            ends_indent=False,
            children=list({
                context
                for pattern in patterns
                for context in contexts_in_pattern(pattern)
            }),
            patterns=patterns,
        )

        patterns_queue = context.patterns[:]
        while len(patterns_queue) > 0:
            pattern = patterns_queue.pop(0)

            pattern_include = pattern.get("include")
            if pattern_include:
                if pattern_include == "pop_when_deindent":
                    context.ends_indent = True

            pattern_match = pattern.get("match")
            if pattern_match:
                if INDENTATION_MARKER in pattern_match:
                    context.starts_indent = True

                pattern_push = pattern.get("push")
                pattern_set = pattern.get("set")
                for pattern_next in [pattern_push, pattern_set]:
                    if pattern_next is None:
                        continue
                    if isinstance(pattern_next, str):
                        pass
                    elif all(isinstance(p, str) for p in pattern_next):
                        pass
                    else:
                        patterns_queue = pattern_next + patterns_queue

        return context

class ContextRegistry:
    def __init__(self):
        self._contexts = {}  # type: dict[str, ContextInfo]

    def __repr__(self):
        return repr(self.all_contexts)

    @cached_property
    def all_contexts(self) -> list[ContextInfo]:
        return list(self._contexts.values())

    def get_context(self, name: str) -> ContextInfo:
        return self._contexts[name]

    @classmethod
    def parse(cls, data: dict) -> "ContextRegistry":
        contexts = cls()

        seen = set()
        queue = ["main", "prototype"]
        while len(queue) > 0:
            context_name = queue.pop(0)
            if context_name in seen:
                continue

            seen.add(context_name)
            context = ContextInfo.parse(
                name=context_name,
                patterns=data["contexts"][context_name],
            )
            contexts._contexts[context_name] = context
            queue.extend(context.children)

        return contexts

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
