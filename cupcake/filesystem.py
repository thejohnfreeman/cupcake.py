from pathlib import Path


def is_modified_after(outfile: Path, infile: Path) -> bool:
    """Return whether an output file was last modified after its input."""
    return (
        infile.is_file() and outfile.is_file() and
        outfile.stat().st_mtime > infile.stat().st_mtime
    )
