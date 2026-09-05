# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jinja2>=3.1.6",
#     "typer>=0.27.0",
# ]
# ///
"""Template new term and role entries for the Word Explainer.

This script generates the directory structure and ``index.qmd`` file for a
new term or role entry, populated from a Jinja template. It must be run from
the project root directory (the folder containing ``words/``).

The script is managed by ``uv``, which handles dependency installation
automatically — no manual ``pip install`` is required.

Usage
-----
Run the script using ``uv run`` from the project root. The contributing guide
provides more information.

Notes
-----
- All definitions must use only the 1000 most used words, following
  the Up-Goer Five convention. Check your definition at
  https://xkcd.com/simplewriter/
- For a full list of options, run ``uv run dev-tools/create.py --help`` or
  ``uv run dev-tools/create.py <command> --help``.
"""

from enum import StrEnum
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader

from pathlib import Path

app = typer.Typer(
    help="Template new term and role entries for the Word Explainer.",
    no_args_is_help=True,
)


def is_in_root_dir() -> None:
    """Check that the script is being run from the project root directory.

    The project root is identified by the presence of a ``words/`` directory.
    This check prevents entries from being created in the wrong location if
    the script is accidentally run from a subdirectory.

    Raises:
        FileNotFoundError: If a ``words/`` directory is not found in the
            current working directory.
    """
    current = Path.cwd()
    if not (current / "words").is_dir():
        raise FileNotFoundError(
            "Could not find 'words' dir. Please run script from project root"
        )


def get_template_dir() -> Path:
    """Return the path to the Jinja templates directory.

    Templates are expected to live at ``dev-tools/templates/`` relative to
    the project root. Each template is named ``<word_type>.qmd.jinja``,
    where ``<word_type>`` is either ``roles`` or ``terms``.

    Returns:
        Path: Absolute path to the ``dev-tools/templates/`` directory.
    """
    return Path.cwd() / "dev-tools" / "templates"


class WordType(StrEnum):
    ROLES = "roles"
    """The type of Word Explainer entry to create.

    Attributes:
        ROLES: Represents a role entry, stored under ``words/roles/``.
        TERMS: Represents a term entry, stored under ``words/terms/``.
    """
    TERMS = "terms"


def load_template(word_type: WordType):
    """Load the Jinja template for the given word type.

    Looks for a template file named ``<word_type>.qmd.jinja`` in the
    templates directory returned by :func:`get_template_dir`.

    Args:
        word_type (WordType): The type of entry to load the template for,
            either ``WordType.ROLES`` or ``WordType.TERMS``.

    Returns:
        jinja2.Template: The loaded Jinja template, ready to be rendered.
    """
    return Environment(loader=FileSystemLoader([str(get_template_dir())])).get_template(
        f"{word_type}.qmd.jinja"
    )


@app.command()
def role(
    role_name: Annotated[str, typer.Option("-r", help="Role name")],
    up_goer_five_name: Annotated[
        str, typer.Option("-u", help="Short Up Goer Five version of the name")
    ],
    description: Annotated[
        str, typer.Option("-d", help="Long description explaining the role")
    ],
    folder_name: Annotated[
        str | None, typer.Option("-f", help="Name of folder to create in src")
    ] = None,
    override: Annotated[
        bool, typer.Option("-o", help="Option to override existing folder/files")
    ] = False,
) -> None:
    """Create a new role entry under ``words/roles/``.

    Creates a new directory for the role and populates an ``index.qmd`` file
    from the roles Jinja template. The folder name defaults to the role name
    in lowercase with spaces replaced by hyphens if not explicitly provided.

    The Up-Goer Five name should be a short, plain-language description of
    the role using only the 1000 most used English words. Check your
    definition at https://xkcd.com/simplewriter/

    Args:
        role_name (str): The full name of the role
            (e.g. ``"Research Software Engineer"``).
        up_goer_five_name (str): A short Up-Goer Five description of the role
        description (str): A longer description explaining the role in more
            detail.
        folder_name (str, optional): The name of the folder to create under
            ``words/roles/``. Defaults to ``role_name`` lowercased with
            spaces replaced by hyphens
            (e.g. ``"Research Software Engineer"`` → ``"research-software-engineer"``).
        override (bool): If ``True``, allows overwriting an existing entry.
            Defaults to ``False``.

    Raises:
        FileExistsError: If the target directory already exists and
            ``override`` is ``False``.
        FileNotFoundError: If the script is not run from the project root.
    """
    if folder_name is None:
        folder_name = role_name.replace(" ", "-").lower()

    is_in_root_dir()
    new_role_dir: Path = Path.cwd() / "words" / "roles" / folder_name

    # Fail if directory already exists when override disabled
    new_role_dir.mkdir(exist_ok=override)
    print(f"Templating new role in {new_role_dir}")

    role_template = load_template(WordType.ROLES)
    print(
        role_template.render(
            role_name=role_name,
            up_goer_five_name=up_goer_five_name,
            description=description,
        ),
        file=Path(new_role_dir / "index.qmd").open(mode="w"),
    )


@app.command()
def term(
    term_name: Annotated[str, typer.Option("-t", help="Name of terminology")],
    noun_def: Annotated[
        str | None, typer.Option("-n", help="Noun definition of the term")
    ] = None,
    noun_description: Annotated[
        str | None, typer.Option("--noun-desc", help="Noun description of the term")
    ] = None,
    verb_def: Annotated[
        str | None, typer.Option("-v", help="Verb definition of the term")
    ] = None,
    verb_description: Annotated[
        str | None, typer.Option("--verb-desc", help="Verb description of the term")
    ] = None,
    folder_name: Annotated[
        str | None, typer.Option("-f", help="Name of folder to be created in src")
    ] = None,
    override: Annotated[
        bool, typer.Option("-o", help="Option to override existing folder/files")
    ] = False,
) -> None:
    """Create a new term entry under ``words/terms/``.

    Creates a new directory for the term and populates an ``index.qmd`` file
    from the terms Jinja template. A term can have a noun definition, a verb
    definition, or both. At least one must be provided. Each definition must
    be accompanied by a corresponding description.

    All definitions must use only the 1000 most common English words,
    following the Up-Goer Five convention. Check your definition at
    https://xkcd.com/simplewriter/

    Args:
        term_name (str): The name of the term (e.g. ``"Version Control"``).
        noun_def (str, optional): The noun definition of the term, using only
            the 1000 most common English words. Required if
            ``noun_description`` is provided.
        noun_description (str, optional): A longer noun description of the
            term. Required if ``noun_def`` is provided.
        verb_def (str, optional): The verb definition of the term, using only
            the 1000 most common English words. Required if
            ``verb_description`` is provided.
        verb_description (str, optional): A longer verb description of the
            term. Required if ``verb_def`` is provided.
        folder_name (str, optional): The name of the folder to create under
            ``words/terms/``. Defaults to ``term_name`` lowercased with
            spaces replaced by hyphens
            (e.g. ``"Version Control"`` → ``"version-control"``).
        override (bool): If ``True``, allows overwriting an existing entry.
            Defaults to ``False``.

    Raises:
        ValueError: If none of the definitions or descriptions are provided.
        ValueError: If a definition is provided without its corresponding
            description, or vice versa.
        FileExistsError: If the target directory already exists and
            ``override`` is ``False``.
        FileNotFoundError: If the script is not run from the project root.
    """
    is_in_root_dir()
    if folder_name is None:
        folder_name = term_name.replace(" ", "-").lower()

    new_terms_dir = Path.cwd() / "words" / "terms" / folder_name
    new_terms_dir.mkdir(exist_ok=override)
    print(f"Templating new role in {new_terms_dir}")

    match (noun_def, noun_description, verb_def, verb_description):
        case (None, None, None, None):
            raise ValueError(
                "None of the definitions or descriptions have been defined"
            )
        case (x, None, _, _) | (_, _, x, None) if x is not None:
            raise ValueError("Definition defined but not the description")
        case (None, x, _, _) | (_, _, None, x) if x is not None:
            raise ValueError("Description defined but not the definition")
        case _:
            ...

    terms_template = load_template(WordType.TERMS)
    print(
        terms_template.render(
            term_name=term_name,
            is_noun=noun_def is not None,
            noun_def=noun_def,
            noun_description=noun_description,
            is_verb=verb_def is not None,
            verb_def=verb_def,
            verb_description=verb_description,
        ),
        file=Path(new_terms_dir / "index.qmd").open(mode="w"),
    )


if __name__ == "__main__":
    is_in_root_dir()
    app()
