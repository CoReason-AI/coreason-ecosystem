# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import click
from coreason_manifest.spec.ontology import WorkflowManifest

from coreason_ecosystem.utils.logger import logger


@click.command()
def main() -> None:
    """CoReason Ecosystem CLI entry point."""
    message = "CoReason Ecosystem Execution Plane Initialized."
    logger.info(message)
    logger.info(f"Manifest schema loaded: {WorkflowManifest.__name__}")
    click.echo(message)


if __name__ == "__main__":  # pragma: no cover
    main()
