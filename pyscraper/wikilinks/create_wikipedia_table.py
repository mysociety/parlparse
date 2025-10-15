"""
This is a script to download and process Wikipedia data dumps into a parquet (with a bloom filter) that
can then be used as part of lookups.

It doesn't need to be frequently run.
"""

import gzip
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import duckdb
import requests
import rich

from pyscraper.settings import settings

DOWNLOAD_DATE = "20250901"
dest_folder = settings.parldata_path / "wikilinks"
temp_folder = Path(tempfile.gettempdir()) / "wikidump"


def create_folders():
    dest_folder = settings.parldata_path / "wikilinks"
    temp_folder = Path(tempfile.gettempdir()) / "wikidump"
    if not dest_folder.exists():
        dest_folder.mkdir(parents=True, exist_ok=True)
    if not temp_folder.exists():
        temp_folder.mkdir(parents=True, exist_ok=True)
    # Also create the processed subfolder in temp
    processed_folder = temp_folder / "processed"
    if not processed_folder.exists():
        processed_folder.mkdir(parents=True, exist_ok=True)


def download_file(url, dest_path):
    """Download a file from a URL with streaming to avoid memory issues."""
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"Downloaded: {dest_path}")


def extract_gzip(gz_path, out_path):
    """Extract a .gz file."""
    with gzip.open(gz_path, "rb") as f_in:
        with open(out_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)  # type: ignore
    print(f"Extracted: {out_path}")


def download_from_url(url: str):
    dest_dir = temp_folder / "raw"
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = os.path.basename(url)
    gz_path = dest_dir / filename
    out_path = gz_path.with_suffix("")  # strip ".gz"

    # Download file
    if not gz_path.exists():
        print("Downloading file...")
        download_file(url, gz_path)
    else:
        print(f"File already exists: {gz_path}")

    # Extract file
    if not os.path.exists(out_path):
        print("Extracting file...")
        extract_gzip(gz_path, out_path)
    else:
        print(f"Extracted file already exists: {out_path}")


def convert_to_sqlite(input_file: Path, output_file: Path) -> Path:
    """
    run the mysql2sqlite shell utility on the input file
    """
    rich.print("Converting from [green]mysql[/green] to [green]sqlite[/green]")
    sqlite_converter = str(Path(__file__).parent / "mysql2sqlite")
    converted_pp = subprocess.run(
        [sqlite_converter, str(input_file)],
        check=True,
        stdout=subprocess.PIPE,
    )

    rich.print(
        f"Converting [green]{input_file}[/green] to [green]{output_file}[/green]"
    )

    # Filter out constraint definitions to avoid integrity errors
    sql_content = converted_pp.stdout.decode("ISO-8859-1")
    filtered_lines = []

    for line in sql_content.splitlines():
        # Skip lines that define constraints (UNIQUE, FOREIGN KEY, CHECK, etc.)
        line_stripped = line.strip()
        if (
            line_stripped.startswith("UNIQUE ")
            or line_stripped.startswith("FOREIGN KEY ")
            or line_stripped.startswith("CHECK ")
            or line_stripped.startswith("CONSTRAINT ")
            or ",  UNIQUE (" in line
            or ", UNIQUE (" in line
        ):
            continue
        filtered_lines.append(line)

    filtered_sql = "\n".join(filtered_lines)

    conn = sqlite3.connect(output_file)
    conn.executescript(filtered_sql)
    conn.commit()
    conn.close()

    return output_file


def sqlite_to_parquet(sqlite_file: Path, parquet_file: Path, table_name: str):
    duck_script = f"""
    ATTACH '{sqlite_file}' (TYPE sqlite);
    USE {table_name};
    SET sqlite_all_varchar=true;
    COPY {table_name} TO '{parquet_file}' (FORMAT parquet);
    """
    duck = duckdb.connect()
    duck.execute(duck_script)
    duck.close()


def process_page_props():
    url = f"https://dumps.wikimedia.org/enwiki/{DOWNLOAD_DATE}/enwiki-{DOWNLOAD_DATE}-page_props.sql.gz"
    download_from_url(url)
    convert_to_sqlite(
        temp_folder / "raw" / f"enwiki-{DOWNLOAD_DATE}-page_props.sql",
        temp_folder / "processed" / "page_props.sqlite",
    )
    sqlite_to_parquet(
        temp_folder / "processed" / "page_props.sqlite",
        temp_folder / "processed" / "page_props.parquet",
        "page_props",
    )


def process_page():
    url = f"https://dumps.wikimedia.org/enwiki/{DOWNLOAD_DATE}/enwiki-{DOWNLOAD_DATE}-page.sql.gz"
    download_from_url(url)
    convert_to_sqlite(
        temp_folder / "raw" / f"enwiki-{DOWNLOAD_DATE}-page.sql",
        temp_folder / "processed" / "page.sqlite",
    )
    sqlite_to_parquet(
        temp_folder / "processed" / "page.sqlite",
        temp_folder / "processed" / "page.parquet",
        "page",
    )


def process_redirects():
    url = f"https://dumps.wikimedia.org/enwiki/{DOWNLOAD_DATE}/enwiki-{DOWNLOAD_DATE}-redirect.sql.gz"
    download_from_url(url)
    convert_to_sqlite(
        temp_folder / "raw" / f"enwiki-{DOWNLOAD_DATE}-redirect.sql",
        temp_folder / "processed" / "redirect.sqlite",
    )
    sqlite_to_parquet(
        temp_folder / "processed" / "redirect.sqlite",
        temp_folder / "processed" / "redirect.parquet",
        "redirect",
    )


def create_combined_file():
    """
    Bring all the pieces together - we want one page table that all the information we need
    """
    duck = duckdb.connect()

    duck.execute(
        f"Create or replace view page_props as (select * from '{temp_folder / 'processed' / 'page_props.parquet'}')"
    )
    duck.execute(
        f"Create or replace view page as (select *  from '{temp_folder / 'processed' / 'page.parquet'}')"
    )
    duck.execute(
        f"Create or replace view redirect as (select *  from '{temp_folder / 'processed' / 'redirect.parquet'}')"
    )

    print("Creating reduced files")
    # reduce the page file to just the 0 namespace (main)
    query = f"""
    COPY(
    SELECT page_id, page_title, page_is_redirect, page_is_new from page where page_namespace = 0
    ) TO '{temp_folder / "processed" / "page_reduced.parquet"}' (FORMAT parquet);
    """
    duck.execute(query)

    # pivot the page_props file to have one row per page with columns for each of the properties we care about
    print("Reducing page_props file")
    query = """
    with pp as (
        select 
            pp_page,
            pp_propname,
            pp_value
        from page_props
        where pp_propname in ('displaytitle', 'wikibase_item', 'wikibase-shortdesc', 'disambiguation')
    )
    select
        pp_page,
        max(case when pp_propname = 'wikibase_item' then pp_value end) as wikibase_item,
        max(case when pp_propname = 'wikibase-shortdesc' then pp_value end) as wikibase_shortdesc,
        max(case when pp_propname = 'disambiguation' then pp_value end) as disambiguation
    from pp
    group by pp_page
    """
    # need to do some extra processing of this in python for type reasons
    df = duck.execute(query).df()
    df = df.set_index("pp_page")
    df["disambiguation"] = df["disambiguation"].notnull()

    df.to_parquet(temp_folder / "processed" / "page_props_reduced.parquet", index=True)

    print("Joining files")
    # time to join the two files
    query = f"""
    CREATE or replace view page_reduced as (select * from '{temp_folder / "processed" / "page_reduced.parquet"}');
    CREATE or replace view page_props_reduced as (select * from '{temp_folder / "processed" / "page_props_reduced.parquet"}');
    COPY(
    Select * exclude(pp_page) from page_reduced join page_props_reduced on (page_reduced.page_id = page_props_reduced.pp_page) 
    ) TO '{temp_folder / "processed" / "page_joined.parquet"}' (FORMAT parquet);
    """
    duck.execute(query)

    print("Adding redirects")
    duck.execute(
        f"Create or replace view page_joined as (select *  from '{temp_folder / 'processed' / 'page_joined.parquet'}')"
    )

    query = f"""
    COPY(
    SELECT
    page_joined.*,
    final_page_title: coalesce(redirect.rd_title, page_joined.page_title)
    from page_joined
    LEFT JOIN redirect on (page_joined.page_id = redirect.rd_from)
    ORDER BY page_title
    ) TO '{dest_folder / "page_with_redirect.parquet"}' (FORMAT parquet);
    """

    duck.execute(query)

    duck.close()


def run_all():
    create_folders()
    process_page_props()
    process_page()
    process_redirects()
    create_combined_file()


if __name__ == "__main__":
    run_all()
