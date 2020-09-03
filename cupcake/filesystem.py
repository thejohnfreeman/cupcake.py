import os
from pathlib import Path


def is_modified_after(outfile: Path, infile: Path) -> bool:
    """Return whether an output file was last modified after its input."""
    return (
        infile.is_file() and outfile.is_file() and
        outfile.stat().st_mtime > infile.stat().st_mtime
    )


def is_under(child: Path, parent: Path) -> bool:
    try:
        Path(child).relative_to(Path(parent))
    except ValueError:
        return False
    return True


def is_hidden(filename: str):
    return filename.startswith('.')


# TODO: Abstract recursive directory search with rich, composable predicates.
def find(directory: Path, ignore: Path = None):
    for prefix, dirnames, filenames in os.walk(directory):
        prefix = Path(prefix)
        dirnames[:] = (
            d for d in dirnames
            if not is_hidden(d) and not is_under(prefix / d, ignore)
        )
        for filename in filenames:
            yield (prefix, filename)


# TODO: Atomic file that creates a temporary file and moves it into place.
