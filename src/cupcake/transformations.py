import libcst as cst
import libcst.matchers
import re
import typing as t

from cupcake import confee

def _remove_includes(lines: t.Iterator[str], file: t.TextIO, name: str):
        edited = False
        comment = False
        for line in lines:
            match = re.match(f'#include\\s+<{name}[/.]', line)
            if not comment and match:
                edited = True
                continue
            file.write(line)
            if comment:
                if re.search(r'\*/', line):
                    comment = False
                continue
            match = re.match(r'(\s*)(#|//|/\*|$)', line)
            if not match:
                break
            if match.group(2) == '/*':
                comment = True
        for line in lines:
            file.write(line)
        if not edited:
            raise confee.CancelOperation()

def remove_includes(pathlike, name):
    """Remove includes of named library from file."""
    with confee.atomic(pathlike, mode='w') as fout:
        with open(pathlike, 'r') as fin:
            _remove_includes(iter(fin), fout, name)

def cstNewLine(indent=''):
    return cst.ParenthesizedWhitespace(
        indent=True,
        last_line=cst.SimpleWhitespace(indent),
    )

class ChangeRequirements(cst.CSTTransformer):

    def __init__(self, properties=['requires']):
        m = cst.matchers
        self.properties = m.OneOf(*map(m.Name, properties))

    def leave_Assign(self, old, new):
        m = cst.matchers
        if len(new.targets) != 1:
            return new
        if not m.matches(new.targets[0].target, self.properties):
            return new
        if not m.matches(
            new.value,
            (m.List | m.Set | m.Tuple)(
                elements=[m.ZeroOrMore(m.Element(value=m.SimpleString()))]
            )
        ):
            raise SystemExit('requirements is not a list of strings')
        matches = [
            re.match(r'^[\'"]([^/]+)/(.*)[\'"]$', e.value.value)
            for e in new.value.elements
        ]
        requirements = {match.group(1): match.string for match in matches}
        requirements = self.change_(requirements)
        requirements = requirements.values()
        requirements = sorted(requirements)
        elements = [
            cst.Element(
                value=cst.SimpleString(requirement),
                comma=cst.Comma(whitespace_after=cstNewLine('    ')),
            ) for requirement in requirements
        ]
        elements[-1] = cst.Element(value=elements[-1].value, comma=cst.Comma())
        return new.with_changes(
            value=new.value.with_changes(
                elements=elements,
                lbracket=cst.LeftSquareBracket(whitespace_after=cstNewLine('    ')),
                rbracket=cst.RightSquareBracket(whitespace_before=cstNewLine()),
            )
        )

class AddRequirement(ChangeRequirements):

    def __init__(self, property, name, reference):
        super().__init__(properties=[property])
        self.name = name
        self.reference = f"'{reference}'"

    def change_(self, requirements):
        if self.name not in requirements:
            requirements[self.name] = self.reference
        return requirements

class RemoveRequirement(ChangeRequirements):

    def __init__(self, name):
        super().__init__(properties=['requires', 'test_requires'])
        self.name = name

    def change_(self, requirements):
        requirements.pop(self.name, None)
        return requirements
