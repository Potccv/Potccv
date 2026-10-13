"""Path checks shared by both scanners, with no filesystem mutation."""

from pathlib import Path
import stat


def is_within(path: Path, root: Path) -> bool:
    """Compare resolved paths, including the root itself."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def is_redirect(path: Path) -> bool:
    """Detect symbolic links and Windows junction/reparse entries."""
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def contains_redirect(path: Path, root: Path) -> bool:
    """Check the lexical path below a trusted root before opening a file."""
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError:
        return True
    if is_redirect(root.absolute()):
        return True
    current = root.absolute()
    for part in relative.parts:
        if part == "..":
            if current == root.absolute():
                return True
            current = current.parent
        else:
            current = current / part
        if is_redirect(current):
            return True
    return False
