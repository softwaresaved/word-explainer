# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "typer>=0.27.0",
# ]
# ///

"""Validate Up-Goer Five word compliance for all entries in the ``words/`` directory.

This script parses ``index.qmd`` files under ``words/roles/`` and
``words/terms/`` and checks that all user-facing text fields use only the
1000 most commonly used words in English, as defined in ``valid_words.txt``.

For **roles**, the following metadata fields are validated:

- ``subtitle``
- ``description``

For **terms**, the following content sections are validated:

- The short definition inside each ``::: {.definition}`` ... ``:::`` block
- The longer description between the end of each definition block and the
  next ``##`` heading (or end of file)

Note
-----

First draft of this was generated with claude-sonnet-4-6

Usage
-----
Run from the project root directory:

.. code-block:: console

    # Validate all entries
    uv run dev-tools/validate.py

    # Validate a specific directory
    uv run dev-tools/validate.py --words-dir words/terms

    # Use a custom word list
    uv run dev-tools/validate.py --valid-words-path path/to/valid_words.txt

Notes
-----
- The script exits with a non-zero status code if any invalid words are found,
  making it suitable for use in CI/CD pipelines.
- Hyphenated words (e.g. ``wonder-driven``) are split and each part validated
  independently.
"""

import re
from pathlib import Path
from typing import Annotated
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

import typer

app = typer.Typer(
    help="Validate Up-Goer Five word compliance for all entries in the words/ directory.",
    no_args_is_help=False,
)

CONSOLE: Console = Console()
ERR_CONSOLE: Console = Console(stderr=True)


def load_valid_words(valid_words_path: Path) -> frozenset[str]:
    """Load the set of valid Up-Goer Five words from a file.

    The file is expected to contain words separated by ``|`` characters on a
    single line. Each word is stripped of whitespace before being added to the
    set.

    Args:
        valid_words_path (Path): Path to the ``valid_words.txt`` file.

    Returns:
        frozenset[str]: An immutable set of valid words for fast membership
        lookup.

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

    Comparison is case-insensitive. Punctuation attached to words is stripped
    before lookup. Hyphenated words (e.g. ``wonder-driven``) are split and
    each part validated independently.

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
        # Remove emojis and other non-ASCII characters, keep only letters/numbers/hyphens
        cleaned = re.sub(r"[^\w\-']", "", raw_word).lower()
        cleaned = cleaned.strip(".,!?;:\"'()-").lower()

        if not cleaned:
            continue

        # Skip if word is purely numeric
        if cleaned.isdigit():
            continue

        # Split hyphenated compounds and validate each part independently
        parts = cleaned.split("-")
        for part in parts:
            if not part:
                continue

            # Skip if part is purely numeric
            if part.isdigit():
                continue

            # Check if word is in valid words
            if part in valid_words or part in seen:
                continue

            # Word is invalid
            seen.add(part)
            invalid.append(part)

    return invalid


def parse_role_fields(content: str) -> dict[str, str]:
    """Extract the ``subtitle`` and ``description`` fields from a role ``index.qmd``.

    Parses the YAML front matter block delimited by ``---`` at the top of the
    file and extracts the values of the ``subtitle`` and ``description`` keys.
    Handles both single-line values and multiline YAML literal block scalars
    (denoted by ``|``).

    Args:
        content (str): The full text content of the ``index.qmd`` file.

    Returns:
        dict[str, str]: A dictionary with keys ``"subtitle"`` and
        ``"description"``, containing the extracted values. Missing fields
        are omitted from the dictionary.
    """
    front_matter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not front_matter_match:
        return {}

    front_matter = front_matter_match.group(1)
    fields: dict[str, str] = {}

    for key in ("subtitle", "description"):
        # Match multiline YAML literal block scalar (key: |)
        multiline_match = re.search(
            rf"^{key}:\s*\|\n((?:[ \t]*.*\n?)*?)(?=^\S|\Z)",
            front_matter,
            re.MULTILINE,
        )
        if multiline_match:
            fields[key] = "\n".join(
                line.strip()
                for line in multiline_match.group(1).splitlines()
                if line.strip()  # skip blank lines when joining
            )
            continue

        # Match single-line values: key: value
        single_match = re.search(
            rf"^{key}:\s*(.+)$",
            front_matter,
            re.MULTILINE,
        )
        if single_match:
            fields[key] = single_match.group(1).strip().strip('"').strip("'")

    return fields


def parse_term_sections(content: str) -> list[dict[str, str]]:
    """Extract definition and description text from a term ``index.qmd``.

    For each ``##`` section in the file, extracts:

    - The word type label from the square brackets in the heading
      (e.g. ``"the name of a thing"`` from
      ``## {{< meta title >}} [the name of a thing]{.word-type}``).
    - The short definition inside the ``::: {.definition}`` ... ``:::`` block.
    - The longer description between the end of the definition block and the
      next ``##`` heading (or end of file).

    Args:
        content (str): The full text content of the ``index.qmd`` file.

    Returns:
        list[dict[str, str]]: A list of dictionaries, one per ``##`` section,
        each containing:

        - ``"word_type"`` — the label extracted from the heading's square
          brackets (e.g. ``"the name of a thing"``).
        - ``"definition"`` — the short definition text (if found).
        - ``"description"`` — the longer description text (if found).
    """
    h2_pattern = re.compile(r"^## .+$", re.MULTILINE)
    headings = [m.group() for m in h2_pattern.finditer(content)]
    chunks = h2_pattern.split(content)[1:]

    sections: list[dict[str, str]] = []

    for heading, chunk in zip(headings, chunks):
        # Extract label from square brackets in heading
        # e.g. "## {{< meta title >}} [the name of a thing]{.word-type}"
        #   →  "the name of a thing"
        word_type_match = re.search(r"\[([^\]]+)\]\{\.word-type\}", heading)
        word_type = word_type_match.group(1) if word_type_match else heading.strip()

        section: dict[str, str] = {"word_type": word_type}

        definition_match = re.search(
            r":::\s*\{\.definition\s*\}(.*?):::",
            chunk,
            re.DOTALL,
        )
        if definition_match:
            section["definition"] = definition_match.group(1).strip()

            after_block = chunk[definition_match.end() :]
            description = after_block.strip()
            if description:
                section["description"] = description

        sections.append(section)

    return sections


def parse_about_page(content: str) -> str:
    """Extract markdown content from about/index.qmd, excluding images and tables.

    Removes:
    - YAML front matter
    - Image syntax including curly bracket attributes: ![alt](url){...}
    - Link URLs (keeps display text): [text](url) → text
    - Markdown tables (detected by pipe-delimited rows)

    Args:
        content (str): The full text content of the ``about/index.qmd`` file.

    Returns:
        str: The cleaned markdown content ready for word validation.
    """
    # Remove YAML front matter
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)

    # Remove image syntax with optional curly bracket attributes
    # Matches: ![alt](url) or ![alt](url){fig-alt="..." fig-align="..."}
    content = re.sub(r"!\[([^\]]*)\]\([^)]+\)(?:\{[^}]*\})?", "", content)

    # Extract link display text, discard URLs: [text](url) → text
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

    # Remove markdown tables: match lines that are pipe-delimited
    # This includes header rows, separator rows (|---|), and data rows
    lines = content.split("\n")
    filtered_lines = []
    for line in lines:
        # Check if line is part of a table (contains pipes and looks like table syntax)
        stripped = line.strip()
        if stripped and "|" in stripped:
            # Check if it's a separator row (|---|) or data row with pipes
            if re.match(r"^\s*\|[\s\-|]+\|\s*$", line) or (
                stripped.startswith("|") and stripped.endswith("|")
            ):
                continue  # Skip table rows
        filtered_lines.append(line)

    content = "\n".join(filtered_lines)

    return content


def validate_role(
    qmd_path: Path,
    valid_words: frozenset[str],
) -> list[str]:
    """Validate the Up-Goer Five fields of a role ``index.qmd`` file.

    Checks the ``subtitle`` and ``description`` metadata fields against the
    valid word list.

    Args:
        qmd_path (Path): Path to the role ``index.qmd`` file.
        valid_words (frozenset[str]): The set of valid words.

    Returns:
        list[str]: A list of human-readable error strings, one per invalid
        field. Empty if all fields are valid.
    """
    content = qmd_path.read_text(encoding="utf-8")
    fields = parse_role_fields(content)
    errors: list[str] = []

    for field_name, field_value in fields.items():
        invalid = find_invalid_words(field_value, valid_words)
        if invalid:
            errors.append(
                f"  [{field_name}] Invalid words: {', '.join(invalid)}\n"
                + f"    Text: {field_value}"
            )

    return errors


def validate_term(
    qmd_path: Path,
    valid_words: frozenset[str],
) -> list[str]:
    """Validate the Up-Goer Five fields of a term ``index.qmd`` file.

    Checks the short definition inside each ``::: {.definition}`` block and
    the longer description that follows it against the valid word list.

    Args:
        qmd_path (Path): Path to the term ``index.qmd`` file.
        valid_words (frozenset[str]): The set of valid words.

    Returns:
        list[str]: A list of human-readable error strings, one per invalid
        field. Empty if all fields are valid.
    """
    content = qmd_path.read_text(encoding="utf-8")
    sections = parse_term_sections(content)
    errors: list[str] = []

    for section in sections:
        word_type = section.get("word_type", "unknown")

        for field_name in ("definition", "description"):
            field_value = section.get(field_name)
            if not field_value:
                continue

            invalid = find_invalid_words(field_value, valid_words)
            if invalid:
                # e.g. "the name of a thing: noun definition"
                #      "the name of a thing: description"
                label = f"{word_type}: {field_name}"
                errors.append(
                    f"  [{label}] Invalid words: {', '.join(invalid)}\n"
                    + f"    Text: {field_value[:80]}{'...' if len(field_value) > 80 else ''}"
                )

    return errors


def validate_about_page(
    qmd_path: Path,
    valid_words: frozenset[str],
) -> list[str]:
    """Validate the Up-Goer Five compliance of about/index.qmd.

    Checks all markdown content (excluding images, link URLs, and tables)
    against the valid word list.

    Args:
        qmd_path (Path): Path to the ``about/index.qmd`` file.
        valid_words (frozenset[str]): The set of valid words.

    Returns:
        list[str]: A list of human-readable error strings. Empty if all
        content is valid.
    """
    content = qmd_path.read_text(encoding="utf-8")
    cleaned_content = parse_about_page(content)
    errors: list[str] = []

    invalid = find_invalid_words(cleaned_content, valid_words)
    if invalid:
        errors.append(
            f"  [about content] Invalid words: {', '.join(invalid)}\n"
            + f"    Text: {cleaned_content[:80]}{'...' if len(cleaned_content) > 80 else ''}"
        )

    return errors


def _format_table_title(path: Path, words_dir: Path) -> str:
    """Format a file path into a human-readable table title.

    Converts an absolute path to a display title of the form
    ``"<Type>: <Name> - <relative_path>"``.

    For example:
    ``/path/to/words/terms/software/index.qmd``
    →  ``"Terms: Software - words/terms/software/index.qmd"``

    Args:
        path (Path): The absolute path to the ``index.qmd`` file.
        words_dir (Path): The root ``words/`` directory, used to compute
            the relative path.

    Returns:
        str: The formatted table title.
    """
    # Compute relative path from the project root (parent of words_dir)
    try:
        relative = path.relative_to(words_dir.parent)
    except ValueError:
        relative = path

    # Extract type (roles/terms) and entry name from path parts
    # words/roles/research-software-engineer/index.qmd
    #   → type="Roles", name="Research Software Engineer"
    parts = relative.parts  # ("words", "roles", "entry-name", "index.qmd")
    if len(parts) >= 3:
        entry_type = parts[1].capitalize()  # "Terms"
        entry_name = parts[2].replace("-", " ").title()  # "Software"
        return f"{entry_type}: {entry_name} - {relative}"
    return str(relative)


def report_results(all_errors: dict[Path, list[str]], words_dir: Path) -> None:
    """Report the results of the Up-Goer Five validation in a formatted table.

    Prints a summary panel and a per-file breakdown of any invalid words
    found. Uses :mod:`rich` for formatted terminal output.

    On success, prints a confirmation message to stdout. On failure, prints
    a detailed error report to stderr.

    Args:
        all_errors (dict[Path, list[str]]): A mapping of file paths to their
            list of error strings, as returned by :func:`validate_role` and
            :func:`validate_term`.
        words_dir (Path): The root directory that was validated, used in the
            summary message.
    """
    if not all_errors:
        CONSOLE.print(
            Panel(
                "[bold green]All entries are valid![/bold green]\n"
                f"[dim]Validated all entries in [cyan]{words_dir}[/cyan][/dim]",
                title="Up-Goer Five Validation",
                border_style="green",
            )
        )
        return

    ERR_CONSOLE.print(
        Panel(
            f"[bold red]Found violations in [cyan]{len(all_errors)}[/cyan] file(s)[/bold red]\n"
            f"[dim]Validated entries in [cyan]{words_dir}[/cyan][/dim]",
            title="Up-Goer Five Validation",
            border_style="red",
        )
    )

    for path, errors in all_errors.items():
        table = Table(
            box=box.ROUNDED,
            border_style="red",
            show_header=True,
            header_style="bold magenta",
            title=_format_table_title(path, words_dir),
            title_style="bold cyan",
            expand=True,
        )
        table.add_column("Field", style="yellow", no_wrap=True)
        table.add_column("Invalid Words", style="red")
        table.add_column("Text Preview", style="dim")

        for error in errors:
            # Re-parse the structured error strings into table columns
            # Format: "  [field] Invalid words: x, y\n    Text: ..."
            field_match = re.search(r"\[(.+?)\]", error)
            words_match = re.search(r"Invalid words: (.+)", error)
            text_match = re.search(r"Text: (.+)", error, re.DOTALL)

            field = field_match.group(1) if field_match else "unknown"
            words = words_match.group(1) if words_match else ""
            text = text_match.group(1).strip()[:60] if text_match else ""
            if text_match and len(text_match.group(1).strip()) > 60:
                text += "..."

            table.add_row(field, words, text)

        ERR_CONSOLE.print(table)
        ERR_CONSOLE.print()

    ERR_CONSOLE.print(
        Panel(
            "[dim]Check your definitions using the "
            "[link=https://xkcd.com/simplewriter/]Up-Goer Five Simple Writer"
            "[/link][/dim]",
            border_style="dim",
        )
    )


@app.command()
def validate(
    words_dir: Annotated[
        Path | None,
        typer.Option(
            "--words-dir",
            "-w",
            help="Path to the words/ directory to validate.",
            exists=True,
            dir_okay=True,
            file_okay=False,
            readable=True,
        ),
    ] = None,
    valid_words_path: Annotated[
        Path | None,
        typer.Option(
            "--valid-words-path",
            "-p",
            help="Path to the valid_words.txt file.",
            exists=True,
            dir_okay=False,
            file_okay=True,
            readable=True,
        ),
    ] = None,
) -> None:
    """Validate all role and term entries in the words/ directory.

    Exits with a non-zero status code if any invalid words are found,
    making it suitable for use in CI/CD pipelines.

    Args:
        words_dir (Path | None): Path to the ``words/`` directory. Defaults
            to ``words/`` in the current working directory if not provided.
            Validated by typer to exist and be a readable directory.
        valid_words_path (Path | None): Path to the ``valid_words.txt`` file.
            Defaults to ``dev-tools/valid_words.txt`` in the current working
            directory if not provided. Validated by typer to exist and be a
            readable file.

    Raises:
        typer.BadParameter: If ``words_dir`` or ``valid_words_path`` are
            provided but do not exist or are not readable — handled
            automatically by typer.
        typer.Exit: With code ``1`` if any invalid words are found, or
            code ``0`` if all entries are valid.
    """
    if words_dir is None:
        words_dir = Path.cwd() / "words"

    if valid_words_path is None:
        valid_words_path = Path.cwd() / "dev-tools" / "valid_words.txt"

    if not words_dir.is_dir():
        typer.echo(f"Error: words directory not found at '{words_dir}'", err=True)
        raise typer.Exit(code=1)

    if not valid_words_path.is_file():
        typer.echo(
            f"Error: valid_words.txt not found at '{valid_words_path}'", err=True
        )
        raise typer.Exit(code=1)

    valid_words = load_valid_words(valid_words_path)

    roles_dir = words_dir / "roles"
    terms_dir = words_dir / "terms"
    about_path = Path.cwd() / "about" / "index.qmd"

    if not roles_dir.is_dir() or not terms_dir.is_dir():
        typer.echo("Error: roles or terms directories are not directories")
        raise typer.Exit(code=1)

    all_errors: dict[Path, list[str]] = {}

    for qmd_path in sorted(roles_dir.rglob("index.qmd")):
        errors = validate_role(qmd_path, valid_words)
        if errors:
            all_errors[qmd_path] = errors

    for qmd_path in sorted(terms_dir.rglob("index.qmd")):
        errors = validate_term(qmd_path, valid_words)
        if errors:
            all_errors[qmd_path] = errors

    if about_path.is_file():
        errors = validate_about_page(about_path, valid_words)
        if errors:
            all_errors[about_path] = errors

    report_results(all_errors, words_dir)

    if all_errors:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
