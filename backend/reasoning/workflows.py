"""Practitioner workflow loading and lookup.

Workflows are markdown files stored under a profile's practitioner_workflows
directory.  Each file corresponds to an analysis family (e.g. ``segmentation.md``)
and encodes the reasoning steps a competent analyst would follow.
"""

from pathlib import Path

from reasoning.profiles import ReasoningProfile


def load_workflow(path: Path) -> str:
    """Read a markdown workflow file and return its content as a string.

    Raises FileNotFoundError if the file does not exist.
    """
    return path.read_text(encoding="utf-8")


def get_workflow_for_block(
    block_impl: str,
    profile: ReasoningProfile,
    base_dir: Path,
) -> str | None:
    """Load the practitioner workflow for a given block implementation.

    Constructs the path as::

        {base_dir}/{profile.practitioner_workflows_dir}/{block_family}.md

    where *block_family* is the stem of *block_impl* (everything before the
    first underscore, or the whole string if no underscore).  This maps
    implementation names like ``segmentation_kmeans`` to the family file
    ``segmentation.md``.

    Returns None if no matching workflow file exists.
    """
    # Derive family name: "segmentation_kmeans" -> "segmentation"
    block_family = block_impl.split("_")[0]

    relative_dir = profile.practitioner_workflows_dir.rstrip("/")
    workflow_path = base_dir / relative_dir / f"{block_family}.md"

    if not workflow_path.is_file():
        return None

    return load_workflow(workflow_path)
