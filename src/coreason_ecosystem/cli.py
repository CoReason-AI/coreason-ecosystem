#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_ecosystem

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
