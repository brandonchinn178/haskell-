#!/usr/bin/env python3

"""
Generate the Haskell syntax definition file.

Sublime Text currently doesn't make it possible to use backreferences
to reference captures beyond a context's immediate parent. To get
around that, we'll just generate a syntax file with every possible
indentation hardcoded.

https://forum.sublimetext.com/t/syntax-definition-explicitly-specify-backref-context/60899
"""

import functools
import yaml
from pathlib import Path
from typing import Any, NamedTuple, Optional

HERE = Path(__file__).parent
TEMPLATE = HERE / "Haskell-Syntax.template.sublime-syntax"
OUTPUT = HERE / "Haskell-Syntax.sublime-syntax"

MAX_INDENTATION = 40
INDENTATIONS = list(range(0, MAX_INDENTATION + 1))[::-1]

INDENTATION_MARKER = "{{INDENTATION}}"

Pattern = dict
Patterns = list[Pattern]
ContextName = str
BranchLabel = str

def main():
    # read in old data
    data = decode_yaml(TEMPLATE.read_text())

    # find all indented contexts
    indented_contexts = IndentedContexts.load(data)

    _pattern_with_indent = functools.partial(
        PatternVisitorIndent.run,
        contexts_to_duplicate=indented_contexts.names,
        branch_points_to_duplicate=indented_contexts.branch_points,
    )

    new_contexts = {}
    def _add_new_context(context_name, indent, patterns):
        if indent is not None:
            context_name = name_with_indent(context_name, indent)
        new_contexts[context_name] = patterns

    # generate new contexts
    for context, patterns in data["contexts"].items():
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

        indentations = INDENTATIONS if context in indented_contexts.names else [None]
        for indent in indentations:
            new_patterns = []

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
    # TODO(nested-indent): remove workaround
    if name == "function":
        return name

    return f"{name}__{indent}"

def indent_regex(indent: int) -> str:
    return r"\s{%d}" % indent

### Finding indented contexts ###

# If the context is in an indented state, this represents the path
# from the context that initially added indentation to the current
# context, to be saved if we ever encounter a "pop_when_deindent"
# context.
#
# None if we're currently along a path that isn't indented yet
IndentedContextPath = Optional[list[ContextName]]

class IndentedContexts(NamedTuple):
    names: set[ContextName]
    branch_points: set[BranchLabel]

    @classmethod
    def load(cls, data: dict) -> "IndentedContexts":
        indented_context_names = {"pop_when_deindent"}
        context_to_branch_point = {}

        context_queue: list[tuple[ContextName, IndentedContextPath]] = [
            ("main", None),
            ("prototype", None),
        ]
        seen = set()
        while len(context_queue) > 0:
            context, path = context_queue.pop(0)

            if context in indented_context_names:
                indented_context_names.update(path or [])
                continue

            # check cycles
            node = (context, None if path is None else tuple(path))
            if (node in seen) or (path and context in path):
                continue
            seen.add(node)

            path = None if path is None else path + [context]
            for pattern in data["contexts"][context]:
                branch_point = pattern.get("branch_point")
                if branch_point:
                    context_to_branch_point[context] = branch_point

                # TODO(nested-indent): when matching indentation within indented context,
                # nest indentation indicators; e.g. `function_signature_start__2__4`, so
                # that we can use 'function__2' as a branch point
                next_path: IndentedContextPath
                if INDENTATION_MARKER in pattern.get("match", "") and path is None:
                    next_path = []
                else:
                    next_path = path

                context_queue.extend(
                    (subcontext, next_path)
                    for subcontext in PatternVisitorGetSubcontexts.run(pattern)
                )

        branch_points = {
            context_to_branch_point[context]
            for context in indented_context_names
            if context in context_to_branch_point
        }

        return cls(indented_context_names, branch_points)

### Pattern ###

class PatternVisitor:
    def on_subcontext(self, subcontext: ContextName) -> Any:
        return subcontext

    def on_branch_label(self, branch_label: BranchLabel) -> Any:
        return branch_label

    def _run(self, pattern: Pattern) -> dict:
        new_pattern = {}

        pattern_include = pattern.get("include")
        if pattern_include:
            new_pattern["include"] = self.on_subcontext(pattern_include)

        pattern_match = pattern.get("match")
        if pattern_match:
            pattern_embed = pattern.get("embed")
            if pattern_embed:
                new_pattern["embed"] = self.on_subcontext(pattern_embed)

            pattern_branches = pattern.get("branch")
            if pattern_branches:
                new_pattern["branch"] = [
                    self.on_subcontext(pattern_branch)
                    for pattern_branch in pattern_branches
                ]

            branch_point = pattern.get("branch_point")
            if branch_point:
                new_pattern["branch_point"] = self.on_branch_label(branch_point)

            branch_fail = pattern.get("fail")
            if branch_fail:
                new_pattern["fail"] = self.on_branch_label(branch_fail)

            for key in ["push", "set"]:
                pattern_next = pattern.get(key)
                if pattern_next is None:
                    continue
                if isinstance(pattern_next, str):
                    new_pattern[key] = self.on_subcontext(pattern_next)
                elif all(isinstance(p, str) for p in pattern_next):
                    new_pattern[key] = [self.on_subcontext(p) for p in pattern_next]
                else:
                    new_pattern[key] = [self._run(p) for p in pattern_next]

        return { **pattern, **new_pattern }

class PatternVisitorGetSubcontexts(PatternVisitor):
    @classmethod
    def run(cls, pattern: Pattern) -> list[ContextName]:
        visitor = cls()
        visitor._run(pattern)
        return visitor._subcontexts

    def __init__(self):
        self._subcontexts = []

    def on_subcontext(self, subcontext: ContextName):
        self._subcontexts.append(subcontext)

class PatternVisitorIndent(PatternVisitor):
    @classmethod
    def run(cls, pattern: Pattern, indent: Optional[int], **kwargs) -> dict:
        if indent is None:
            return pattern
        return cls(indent=indent, **kwargs)._run(pattern)

    def __init__(
        self,
        *,
        indent: int,
        contexts_to_duplicate: set[ContextName],
        branch_points_to_duplicate: set[BranchLabel],
    ):
        self._indent = indent
        self._contexts_to_duplicate = contexts_to_duplicate
        self._branch_points_to_duplicate = branch_points_to_duplicate

    def on_subcontext(self, context_name: ContextName) -> ContextName:
        if context_name not in self._contexts_to_duplicate:
            return super().on_subcontext(context_name)
        return name_with_indent(context_name, self._indent)

    # TODO(nested-indent): generalize this to set indentation of branch_point
    # to the appropriate indentation, instead of the current indentation
    def on_branch_label(self, branch_label: BranchLabel) -> BranchLabel:
        if branch_label not in self._branch_points_to_duplicate:
            return super().on_branch_label(branch_label)
        return name_with_indent(branch_label, self._indent)

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
