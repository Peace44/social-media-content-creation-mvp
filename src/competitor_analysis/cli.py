from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from competitor_analysis import config  # noqa: F401 (triggers dotenv load)

app = typer.Typer(
    name="competitor-analysis",
    help="Social media competitor analysis tool powered by Claude AI.",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    profile_url: Annotated[str, typer.Argument(help="Social media profile URL to analyze")],
    max_competitors: Annotated[int, typer.Option("--max-competitors", "-n", help="Max competitors to find")] = 10,
    output_format: Annotated[str, typer.Option("--output-format", "-f", help="Output format: table, csv, excel")] = "table",
    output_file: Annotated[Path | None, typer.Option("--output-file", "-o", help="Output file path (for csv/excel)")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed progress")] = False,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Disable result caching")] = False,
) -> None:
    """Analyze a social media profile and identify its direct competitors."""
    use_cache = not no_cache

    if output_format not in ("table", "csv", "excel"):
        console.print(f"[red]Invalid output format: {output_format}. Choose from: table, csv, excel[/red]")
        raise typer.Exit(1)

    if output_format in ("csv", "excel") and output_file is None:
        console.print(f"[red]--output-file is required when --output-format is {output_format}[/red]")
        raise typer.Exit(1)

    from competitor_analysis.analysis.competitor_finder import analyze_profile, find_competitors
    from competitor_analysis.analysis.kpi_analyzer import gather_kpis
    from competitor_analysis.output.table import render_table
    from competitor_analysis.output.export import export_csv, export_excel
    from competitor_analysis.scraper.profile import scrape_profile

    console.print(f"\n[bold cyan]Competitor Analysis[/bold cyan] — analyzing [underline]{profile_url}[/underline]\n")

    # Stage 1: Scrape & analyze the input profile
    with console.status("[bold]Scraping profile...[/bold]"):
        raw_profile = scrape_profile(profile_url, verbose=verbose)

    with console.status("[bold]Analyzing profile with Claude...[/bold]"):
        profile = analyze_profile(raw_profile, profile_url, verbose=verbose)

    console.print(f"[green]✓[/green] Profile identified: [bold]{profile.name}[/bold] — {profile.niche}")
    if verbose:
        console.print(f"  Target: {profile.target_audience}")
        console.print(f"  Services: {', '.join(profile.services)}")

    # Stage 2: Find competitors
    with console.status("[bold]Searching for competitors...[/bold]"):
        candidates = find_competitors(profile, max_results=max_competitors, use_cache=use_cache, verbose=verbose)

    console.print(f"[green]✓[/green] Found [bold]{len(candidates)}[/bold] competitor candidates")

    # Stage 3: Gather KPIs per competitor
    rows = gather_kpis(candidates, profile, use_cache=use_cache, verbose=verbose, console=console)

    console.print(f"\n[green]✓[/green] Analysis complete — [bold]{len(rows)}[/bold] competitors\n")

    # Stage 4: Output
    if output_format == "table":
        render_table(rows, console=console)
    elif output_format == "csv":
        export_csv(rows, output_file)
        console.print(f"[green]✓[/green] Saved to [bold]{output_file}[/bold]")
    elif output_format == "excel":
        export_excel(rows, output_file)
        console.print(f"[green]✓[/green] Saved to [bold]{output_file}[/bold]")


if __name__ == "__main__":
    app()
