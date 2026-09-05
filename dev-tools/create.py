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

The script is managed by ``uv``, which handles dependency management
automatically.

The up goer five contents are validated against the words from:
https://xkcd.com/simplewriter/words.js. These are stored in ``valid_words.txt``

Usage
-----
Run the script using ``uv run`` from the project root. The contributing guide
provides more information.

Notes
-----
- All definitions are automatically validated against the Up-Goer Five word
  list at parse time. If a definition contains invalid words, the script will
  exit with an error listing the offending words before any files are written.
  The ``valid_words.txt`` file must be present in the project root for
  validation to work.
- We recommend drafting your definition using the
  `Up-Goer Five Simple Writer <https://xkcd.com/simplewriter/>`_ before running
  the script — it gives a more visual and iterative experience than a CLI
  error message.
- For a full list of options, run ``uv run dev-tools/create.py --help`` or
  ``uv run dev-tools/create.py <command> --help``.
"""

from enum import StrEnum
from typing import Annotated, Callable

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


def get_valid_words_path() -> Path:
    """Return the path to valid up goer five words

    Templates are expected to live at ``dev-tools/valid_words.txt`` relative to
    the project root.

    Returns:
        Path: Absolute path to the ``valid_words.txt`` file
    """
    return Path.cwd() / "dev-tools" / "valid_words.txt"


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


def load_valid_words(valid_words_path: Path) -> frozenset[str]:
    """Load the set of valid Up-Goer Five words from a file.

    The file is expected to contain words separated by ``|`` characters on a
    single line. Each word is stripped of whitespace before being added to the
    set.

    Args:
        valid_words_path (Path): Path to the ``valid_words.txt`` file.

    Returns:
        frozenset[str]: An immutable set of valid words for fast membership
        lookup. A ``frozenset`` is used over a ``set`` as the word list is
        read-only after loading.

    Raises:
        FileNotFoundError: If the file does not exist at the given path.
    """
    return frozenset(
        word.strip()
        for word in valid_words_path.read_text(encoding="utf-8").split("|")
        if word.strip()
    )


def find_invalid_words(text: str, valid_words: frozenset[str]) -> list[str]:
    """Identify words in ``text`` that are not in the Up-Goer Five word list.

    Comparison is case-insensitive. Punctuation attached to words
    (e.g. trailing commas, full stops, or apostrophes in contractions) is
    stripped before lookup so that ``"running,"`` and ``"running"`` are
    treated as the same word.

    Args:
        text (str): The text to validate.
        valid_words (frozenset[str]): The set of valid words loaded by
            :func:`load_valid_words`.

    Returns:
        list[str]: A list of unique invalid words found in ``text``,
        preserving the order in which they first appear. Returns an empty
        list if all words are valid.
    """
    seen: set[str] = set()
    invalid: list[str] = []

    for raw_word in text.split():
        cleaned = raw_word.strip(".,!?;:\"'()-").lower()

        if not cleaned:
            continue

        # Split hyphenated words and validate each part independently
        # e.g. "wonder-driven" → ["wonder", "driven"]
        parts = cleaned.split("-")

        for part in parts:
            if not part:
                # Guard against leading/trailing hyphens e.g. "--option"
                continue

            if part not in valid_words and part not in seen:
                seen.add(part)
                invalid.append(part)

    return invalid


def make_up_goer_five_callback() -> Callable[[typer.Context, str | None], str | None]:
    """Create a typer callback that validates a string against the Up-Goer Five word list.

    Returns a callback suitable for use with ``typer.Option(..., callback=...)``.
    The callback is a no-op if the value is ``None``, allowing it to be safely
    used on optional parameters.

    Args:
        valid_words_path (Path): Path to the ``valid_words.txt`` file.
            Defaults to ``valid_words.txt`` in the current working directory.

    Returns:
        Callable[[str | None], str | None]: A typer-compatible callback that
        raises :exc:`typer.BadParameter` if the value contains words not in
        the Up-Goer Five word list, or returns the value unchanged if valid.

    Raises:
        FileNotFoundError: If ``valid_words_path`` does not exist when the
            callback is first invoked.

    Example:
        .. code-block:: python

            up_goer_callback = make_up_goer_five_callback()

            def role(
                description: Annotated[
                    str,
                    typer.Option("-d", callback=up_goer_callback),
                ],
            ) -> None:
                ...
    """
    valid_words_path: Path = get_valid_words_path()
    # Load once at callback creation time rather than on every invocation
    valid_words: frozenset[str] = load_valid_words(valid_words_path)

    def callback(
        ctx: typer.Context,
        value: str | None,
    ) -> str | None:
        """Validate a single CLI parameter value against the Up-Goer Five word list.

        Args:
            ctx (typer.Context): The typer context for the current command.
                Unused but required by the typer callback signature.
            param (typer.CallbackParam): The parameter being validated.
                Unused but required by the typer callback signature.
            value (str | None): The value to validate. If ``None``, the
                callback returns immediately without validation.

        Returns:
            str | None: The original value, unchanged, if valid or ``None``.

        Raises:
            typer.BadParameter: If ``value`` contains words not in the
                Up-Goer Five word list.
        """
        if ctx.resilient_parsing:
            return

        if value is None:
            return value

        invalid_words = find_invalid_words(value, valid_words)
        if invalid_words:
            raise typer.BadParameter(
                "Contains words not in the Up-Goer Five word list: "
                + f"{', '.join(invalid_words)}\n"
                + "Check your definition at https://xkcd.com/simplewriter/"
            )
        return value

    return callback


UP_GOER_CALLBACK = make_up_goer_five_callback()


@app.command()
def role(
    role_name: Annotated[str, typer.Option("-r", help="Role name")],
    up_goer_five_name: Annotated[
        str,
        typer.Option(
            "-u",
            help="Short Up Goer Five version of the name",
            callback=UP_GOER_CALLBACK,
        ),
    ],
    description: Annotated[
        str,
        typer.Option(
            "-d",
            help="Long description explaining the role",
            callback=UP_GOER_CALLBACK,
        ),
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
            Validated automatically against ``valid_words.txt`` at parse time.
        description (str): A longer description explaining the role in more
            detail. Validated automatically against ``valid_words.txt`` at parse time.
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
        typer.BadParameter: If ``up_goer_five_name`` or ``description`` contain
            words not in the Up-Goer Five word list. The error message lists the
            offending words and links to the Simple Writer.
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
        str | None,
        typer.Option(
            "-n",
            help="Noun definition of the term",
            callback=UP_GOER_CALLBACK,
        ),
    ] = None,
    noun_description: Annotated[
        str | None,
        typer.Option(
            "--noun-desc",
            help="Noun description of the term",
            callback=UP_GOER_CALLBACK,
        ),
    ] = None,
    verb_def: Annotated[
        str | None,
        typer.Option(
            "-v",
            help="Verb definition of the term",
            callback=UP_GOER_CALLBACK,
        ),
    ] = None,
    verb_description: Annotated[
        str | None,
        typer.Option(
            "--verb-desc",
            help="Verb description of the term",
            callback=UP_GOER_CALLBACK,
        ),
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
            ``noun_description`` is provided.  Validated automatically against ``valid_words.txt`` at parse time.
        noun_description (str, optional): A longer noun description of the
            term. Required if ``noun_def`` is provided.  Validated automatically against ``valid_words.txt`` at parse time.
        verb_def (str, optional): The verb definition of the term, using only
            the 1000 most common English words. Required if
            ``verb_description`` is provided.  Validated automatically against ``valid_words.txt`` at parse time.
        verb_description (str, optional): A longer verb description of the
            term. Required if ``verb_def`` is provided.  Validated automatically against ``valid_words.txt`` at parse time.
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
        typer.BadParameter: If any of ``noun_def``, ``noun_description``,
            ``verb_def``, or ``verb_description`` contain words not in the
            Up-Goer Five word list. The error message lists the offending words
            and links to the Simple Writer.
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
