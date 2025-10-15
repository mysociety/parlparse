from typer import Typer

app = Typer(pretty_exceptions_enable=False)


@app.command()
def create_wikipedia_table():
    """
    Create parquet file from wikipedia dump.
    """
    from .create_wikipedia_table import run_all

    run_all()


@app.command()
def process_transcripts(
    folder: str = "debates",
    pattern: str = "debates202*",
    include_relevance_check: bool = False,
    override: bool = False,
    export: bool = False,
):
    """
    Extract wikilinks from all transcripts matching the given date pattern (e.g. '2023-05-*').
    """
    from .funcs import TranscriptProcesssor

    TranscriptProcesssor().process_transcript_pattern(
        folder=folder,
        pattern=pattern,
        include_relevance_check=include_relevance_check,
        override=override,
    )

    if export:
        export_lists()


@app.command()
def relevance_check(pattern: str, skip_if_any: bool = True, export: bool = False):
    """
    Run LLM relevance check
    """

    from .funcs import TranscriptProcesssor

    TranscriptProcesssor().process_relevance_check(pattern, skip_if_any=skip_if_any)

    if export:
        export_lists()


@app.command()
def export_lists():
    """
    Export allowlist and blocklist from annotations.
    """
    from .funcs import export_lists

    export_lists()


if __name__ == "__main__":
    app()
