from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich import box

from competitor_analysis.models import CompetitorRow

_PLATFORMS = ["instagram", "facebook", "linkedin", "youtube", "tiktok"]


def _followers_cell(row: CompetitorRow) -> str:
    parts = []
    for p in _PLATFORMS:
        count = row.kpis.follower_count.get(p, "N/A")
        if count and count != "N/A":
            parts.append(f"{p.capitalize()}: {count}")
    return "\n".join(parts) if parts else "N/A"


def _social_cell(row: CompetitorRow) -> str:
    parts = []
    for platform, url in row.social_profiles.items():
        parts.append(f"{platform}: {url}")
    return "\n".join(parts) if parts else "N/A"


def _structure_cell(row: CompetitorRow) -> str:
    checks = {
        "website": "Website",
        "landing_page": "Landing page",
        "ebook": "E-book",
        "freebie": "Freebie",
        "multi_platform": "Multi-platform",
    }
    present = [label for key, label in checks.items() if row.kpis.structure.get(key)]
    return ", ".join(present) if present else "N/A"


def render_table(rows: list[CompetitorRow], console: Console | None = None) -> None:
    """Render the competitor analysis as a Rich table."""
    if console is None:
        console = Console()

    table = Table(
        title="Competitor Analysis",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
        expand=True,
    )

    table.add_column("#", style="dim", width=3, no_wrap=True)
    table.add_column("Name", style="bold", min_width=16, no_wrap=True)
    table.add_column("Description & Info", min_width=24)
    table.add_column("Activities", min_width=20)
    table.add_column("Active Since", width=12, no_wrap=True)
    table.add_column("Social Profiles", min_width=22)
    table.add_column("Website & Links", min_width=20)
    table.add_column("Followers", min_width=18)
    table.add_column("Engagement", width=10, no_wrap=True)
    table.add_column("Structure", min_width=18)
    table.add_column("Why a Competitor", min_width=24)

    for i, row in enumerate(rows, 1):
        table.add_row(
            str(i),
            row.name,
            row.description,
            row.activities,
            row.active_since,
            _social_cell(row),
            "\n".join(row.website_and_links) or "N/A",
            _followers_cell(row),
            row.kpis.interaction_score,
            _structure_cell(row),
            row.why_competitor,
        )

    console.print(table)
