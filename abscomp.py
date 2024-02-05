#!/usr/bin/env python3
"""Compare 2 Audiobookshelf libraries and output various json and csv files showing the difference."""


__author__ = 'Brandon Wells'
__email__ = 'b.w.prog@outlook.com'
__license__ = 'GPLv3+'
__update__ = '2024.02.04'
__version__ = '0.3.0'


import csv
import json
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Annotated

import requests
import typer
from requests import Response
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.traceback import install

PROG_TIME_START: float = perf_counter()
NOW: str = datetime.now(tz=timezone(offset=timedelta(hours=-5))).strftime('%y%m%d')
FILEBASE: str = f'abscomp_books_{NOW}_'


install()
con: Console = Console()
app: Callable[..., None] = typer.Typer(rich_markup_mode='rich')

# ~~~ #
@dataclass(eq=True, frozen=True)
class Book:
    """Hold the important contents of audiobooks."""

    id: str
    title: str
    author: str
    series: str
    year: str
    asin: str
    isbn: str
    added: str
    files: str
    size: str


# ~~~ #
def load_config(file: Path) -> dict[str, dict[str, str]]:
    """Load the TOML config file, validate schema, and print the config.

    Parameters
    ----------
    file : Path
        the TOML config file to load

    Returns
    -------
    dict[str, dict[str, str]]
        the config as a dict

    Raises
    ------
    typer.Exit
        exit on invalid config file
    """
    # load to toml config file
    with file.open(mode='rb') as f:
        config: dict[str, dict[str, str]] = tomllib.load(f)
    # validate toml schema
    match config:
        case {
            'schema': {'version': '1'},
            'abs_lib_one': {
                'url': str(),
                'token': str(),
                'library': str(),
            },
            'abs_lib_two': {
                'url': str(),
                'token': str(),
                'library': str(),
            },
        }:
            # print a copy of the config in a Panel
            config_text: Text = Text(text='', tab_size=4)
            for k, v in config.items():
                if k == next(iter(config)):
                    config_text.append(text=f'{k}:', style='medium_orchid')
                else:
                    config_text.append(text=f'\n{k}:', style='medium_orchid')
                for k2, v2 in v.items():
                    config_text.append(text=f'\n\t{k2}: ', style='green')
                    config_text.append(text=v2)
            con.print(Panel(
                config_text,
                title=f'Loaded Config from: {file}',
                title_align='left',
                border_style='light_green',
                width=60,
                highlight=True,
                expand=False,
                padding=1,
            ))

            return config
        case _:
            con.print(f'[red]ERROR[/]: Invalid Configuration in config file: {file}\n{config}')
            raise typer.Exit(code=1)


# ~~~ #
def get_library(
        url: str,
        token: str,
        lib_id: str,
        lib_num: str,
) -> dict[str, Book]:
    """Return a json/dict of the library contents.

    Parameters
    ----------
    url : str
        base url connection
    token : str
        user ID API token
    lib_id : str
        library specific ID
    lib_num : str
        identify which library is being retrieved

    Returns
    -------
    dict[str, Book]
        dict with title keys and book contents in a Book class

    Raises
    ------
    typer.Exit
        exit on invalid JSON data received from the library
    """
    con.print(f'Retrieving library {lib_num}: {url}', style='green')

    headers: dict[str, str] = {'Authorization': f'Bearer {token}'}
    api_url: str = f'{url}/api/libraries/{lib_id}/items?sort=media.metadata.authorName'

    response: Response = requests.get(url=api_url, headers=headers, timeout=(10, 30))
    response.raise_for_status()

    # strip out just the data needed, put each book into a Book dataclass, then put each Book into the library dict
    try:
        title_library: dict[str, Book] = {}
        for result in response.json()['results']:
            title_library[result['id']] = Book(
                id=result['id'],
                title=result['media']['metadata']['title'],
                author=result['media']['metadata']['authorName'],
                series=result['media']['metadata']['seriesName'],
                year=result['media']['metadata']['publishedYear'],
                asin=result['media']['metadata']['asin'],
                isbn=result['media']['metadata']['isbn'],
                added=result['addedAt'],
                files=result['media']['numAudioFiles'],
                size=result['media']['size'],
            )
    except json.JSONDecodeError as e:
        con.print(f'[red]ERROR:[/] Invalid JSON data. Library may have disconnected mid-transfer.\n\t{e}')
        raise typer.Exit(code=1) from None

    return title_library  # type: ignore  # noqa: PGH003


# ~~~ #
def write_output(
        contents: dict[str, Book],
        out_type: str,
        flag_j: bool,
        flag_c: bool,
) -> None:
    """Write csv and json differences to files.

    Parameters
    ----------
    contents : dict[str, Book]
        The data to output to files.
    out_type : str
        string to add to write 'missing' or 'both' to the file name
    """
    if flag_c:
        # write out as csv
        with Path.open(self=Path(f'{FILEBASE}{out_type}.csv'), mode='w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['Title', 'Author', 'Series', 'Year', 'asin', 'isbn'])

            for audiobook in contents.values():
                csv_writer.writerow([*asdict(obj=audiobook).values()])

    if flag_j:
        # convert the dataclass to dict for json
        content_json: dict[str, dict[str, str]] = {}
        for k, v in contents.items():
            content_json[k] = asdict(obj=v)

        # write out as json
        with Path.open(self=Path(f'{FILEBASE}{out_type}.json'), mode='w', encoding='utf-8') as json_file:
            json.dump(obj=content_json, fp=json_file, ensure_ascii=False, indent=4)


# ~~~ #
def compare_libs(
        lib_one: dict[str, Book],
        lib_two: dict[str, Book],
) -> dict[str, dict[str, Book]]:
    """Compare keys in first dict to second.

    Parameters
    ----------
    lib_one : dict[str, Book]
        first dictionary; the keys of this will be used to lookup keys in second
    lib_two : dict[str, Book]
        second dictionary

    Returns
    -------
    dict[str, dict[str, Book]]
        a 'missing' and a 'both' dictionaries returned together in one dictionary
    """
    # con.print(f'Entered compare_libs [grey50](first entry: {next(iter(lib_one))}[/])', style='green')
    both_books: dict[str, Book] = {}
    missing_books: dict[str, Book] = {}

    for ab_one in lib_one:
        if ab_one in lib_two:
            both_books[ab_one] = lib_one[ab_one]
        else:
            missing_books[ab_one] = lib_one[ab_one]

    # con.print(f' - Missing ASIN count: {len(missing_books)} [grey50](in both: {len(both_books)})[/]',
            #   style='orange_red1')
    return {'both': both_books, 'missing': missing_books}


# ~~~ #
@app.command()
def main(
        file: Annotated[Path, typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            rich_help_panel='[blue]CONFIG FILE[/]',
            help='the TOML config file with the connection details of the libraries to compare',
        )] = Path('absconfig.toml'),
        flag_c_csv: Annotated[bool, typer.Option(
            '-c',
            '--csv',
            rich_help_panel='[yellow]ABSComp Options[/]',
            help='output csv files',
        )] = False,
        flag_j_json: Annotated[bool, typer.Option(
            '-j',
            '--json',
            rich_help_panel='[yellow]ABSComp Options[/]',
            help='output json files',
        )] = False,
) -> None:
    """Compare the contents of two AudioBookShelf Libraries."""
    con.print(f'abscomp.py - {__version__} - ({__update__})\n')

    # load config file, validate schema, and print config in a Panel
    config: dict[str, dict[str, str]] = load_config(file=file)

    # get libraries
    lib_one_start_time: float = perf_counter()
    lib_one: dict[str, Book] = get_library(
        url=config['abs_lib_one']['url'],
        token=config['abs_lib_one']['token'],
        lib_id=config['abs_lib_one']['library'],
        lib_num='One',
    )
    lib_one_end_time: float = perf_counter() - lib_one_start_time
    con.print(f'\t└─❯ ([blue]{lib_one_end_time:.4f}[/]s)')

    lib_two_start_time: float = perf_counter()
    lib_two: dict[str, Book] = get_library(
        url=config['abs_lib_two']['url'],
        token=config['abs_lib_two']['token'],
        lib_id=config['abs_lib_two']['library'],
        lib_num='Two',
    )
    lib_two_end_time: float = perf_counter() - lib_two_start_time
    con.print(f'\t└─❯ ([green]{lib_two_end_time:.4f}[/]s)')

    # create asin keyed libraries for easy comparison (this drops anything without an asin or duplicates with same asin)
    lib_one_asin: dict[str, Book] = {}
    lib_two_asin: dict[str, Book] = {}
    for ab in lib_one.values():
        if ab.asin and ab.asin not in lib_one_asin:
            lib_one_asin[ab.asin] = ab
    for ab in lib_two.values():
        if ab.asin and ab.asin not in lib_two_asin:
            lib_two_asin[ab.asin] = ab

    # first comparison gets asin's missing in Lib Two
    first_compare: dict[str, dict[str, Book]] = compare_libs(lib_one=lib_one_asin, lib_two=lib_two_asin)

    # second comparison gets asin's missing in Lib One
    second_compare: dict[str, dict[str, Book]] = compare_libs(lib_one=lib_two_asin, lib_two=lib_one_asin)

    # output contents of both to files
    write_output(contents=first_compare['both'], out_type='both', flag_c=flag_c_csv, flag_j=flag_j_json)
    write_output(contents=lib_one, out_type='one', flag_c=flag_c_csv, flag_j=flag_j_json)
    write_output(contents=lib_two, out_type='two_full', flag_c=flag_c_csv, flag_j=flag_j_json)

    one_asin_len: int = len(lib_one_asin)
    two_asin_len: int = len(lib_two_asin)
    one_missing_len: int = len(second_compare['missing'])
    two_missing_len: int = len(first_compare['missing'])
    len_both: int = len(first_compare['both'])
    con.print(Panel(
        ('Library One:'
         f'\n\t[medium_orchid]- Unique Entries:[/]\t{len(lib_one)}'
         f'\n\t[medium_orchid]- Unique ASINs:[/]\t\t{one_asin_len}'
         f'\n\t[orange1]- Missing ASINs:[/]\t{one_missing_len} [grey50](ASINs in Lib Two not in Lib One)[/]\t\t'
        '\nLibrary Two:'
         f'\n\t[medium_orchid]- Unique Entries:[/]\t{len(lib_two)}'
         f'\n\t[medium_orchid]- Unique ASINs:[/]\t\t{two_asin_len}'
         f'\n\t[orange1]- Missing ASINs:[/]\t{two_missing_len} [grey50](ASINs in Lib One not in Lib Two)[/]\t\t'
         f'\n\b[green]ASINs in Both Libraries:[/]\t{len_both}'),
         title='Library Details',
         title_align='left',
         border_style='light_green',
         highlight=True,
         width=60,
         expand=False,
         padding=1,
        ),
    )

    # exit the app
    prog_time_total: float = perf_counter() - PROG_TIME_START
    con.print(Panel(
        f':glowing_star: Complete :glowing_star: ([green]{prog_time_total:.4f}[/]s)',
         border_style='light_green',
         highlight=False,
         expand=False,
         padding=1,
        ),
    )


# ~~~ #
if __name__ == '__main__':

    app()
