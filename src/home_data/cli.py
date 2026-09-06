import logging
from pathlib import Path
from typing import Annotated

import typer

from home_data.logging_config import configure_logging
from home_data.operations import run_free_cloud_refresh
from home_data.pipeline import build_gold, build_official_gold, build_roi_gold, ingest_source
from home_data.settings import Settings
from home_data.storage import LocalMedallionStore

app = typer.Typer(help="Victorian home data medallion pipeline")
LOGGER = logging.getLogger(__name__)


@app.command()
def init(data_root: Path | None = None) -> None:
    configure_logging()
    settings = Settings()
    root = data_root or settings.data_root
    LocalMedallionStore(root).initialise()
    typer.echo(f"Initialised medallion storage at {root.resolve()}")


@app.command()
def run(
    source: Annotated[str, typer.Option("--source", help="Configured source adapter name")],
    data_root: Path | None = None,
    input_dir: Annotated[
        Path | None,
        typer.Option("--input-dir", help="Optional directory containing manually downloaded files"),
    ] = None,
) -> None:
    configure_logging()
    settings = Settings()
    root = data_root or settings.data_root
    store = LocalMedallionStore(root)
    store.initialise()
    try:
        manifests = ingest_source(source, store, input_dir=input_dir)
    except Exception:
        LOGGER.exception("Pipeline failed", extra={"source": source, "stage": "failed"})
        raise typer.Exit(code=1)
    run_ids = ",".join(manifest.run_id for manifest in manifests)
    typer.echo(f"Promoted {source} to Silver; run_ids={run_ids}")


@app.command("build-gold")
def build_gold_command(data_root: Path | None = None) -> None:
    configure_logging()
    settings = Settings()
    path = build_gold(data_root or settings.data_root)
    typer.echo(f"Built Gold mart at {path.resolve()}")


@app.command("build-official-gold")
def build_official_gold_command(data_root: Path | None = None) -> None:
    configure_logging()
    settings = Settings()
    paths = build_official_gold(data_root or settings.data_root)
    typer.echo("Built official Gold histories: " + ", ".join(str(path.resolve()) for path in paths))


@app.command("build-roi")
def build_roi_command(
    data_root: Path | None = None,
    crosswalk: Path = Path("config/geography_crosswalk.csv"),
) -> None:
    configure_logging()
    settings = Settings()
    paths = build_roi_gold(data_root or settings.data_root, crosswalk)
    typer.echo("Built governed ROI products: " + ", ".join(str(path.resolve()) for path in paths))


@app.command("free-cloud-refresh")
def free_cloud_refresh_command(data_root: Path = Path("data")) -> None:
    configure_logging()
    try:
        status = run_free_cloud_refresh(data_root)
    except Exception:
        LOGGER.exception("Free-cloud refresh failed", extra={"stage": "failed"})
        raise typer.Exit(code=1)
    typer.echo(f"Free-cloud refresh completed: {status}")
