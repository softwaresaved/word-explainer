# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "jinja2>=3.1.6",
#     "typer>=0.27.0",
# ]
# ///

from enum import StrEnum
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader

from pathlib import Path

app = typer.Typer()


def is_in_root_dir() -> None:
    current = Path.cwd()
    if not (current / "words").is_dir():
        raise FileNotFoundError(
            "Could not find 'words' dir. Please run script from project root"
        )


def get_template_dir() -> Path:
    return Path.cwd() / "dev-tools" / "templates"


class WordType(StrEnum):
    ROLES = "roles"
    TERMS = "terms"


def load_template(word_type: WordType):
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
