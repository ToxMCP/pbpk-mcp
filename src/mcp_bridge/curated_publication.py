from __future__ import annotations

from pathlib import Path


CURATED_PUBLICATION_MODEL_RELATIVE_PATHS = (
    Path("var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R"),
)


def curated_publication_model_relative_paths() -> tuple[str, ...]:
    return tuple(path.as_posix() for path in CURATED_PUBLICATION_MODEL_RELATIVE_PATHS)


def curated_publication_model_paths(workspace_root: Path) -> tuple[Path, ...]:
    root = workspace_root.resolve()
    return tuple(
        (root / relative_path).resolve()
        for relative_path in CURATED_PUBLICATION_MODEL_RELATIVE_PATHS
    )


def curated_publication_model_cli_args(workspace_root: Path) -> list[str]:
    args: list[str] = []
    for path in curated_publication_model_paths(workspace_root):
        args.extend(["--path", str(path)])
    return args
