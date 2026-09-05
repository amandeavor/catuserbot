"""Extract ordinary tar members without permitting links or path escapes."""
from pathlib import Path, PurePosixPath, PureWindowsPath


def extract_tar_safely(archive, destination):
    root = Path(destination).resolve()
    members = archive.getmembers()
    for member in members:
        name = member.name.replace("\\", "/")
        target = (root / name).resolve()
        if (PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
                or ".." in PurePosixPath(name).parts
                or (target != root and root not in target.parents)):
            raise ValueError("Archive member escapes extraction directory")
        if not (member.isfile() or member.isdir()):
            raise ValueError("Archive links and special files are not supported")
    # Validate the full archive before writing any member. No links are extracted.
    archive.extractall(root, members=members)
