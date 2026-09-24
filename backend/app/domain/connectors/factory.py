"""OpenNotebook — connector factory.

Builds a connector instance from its type and configuration so the API and the
scheduled sync task share one mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.connectors.base import BaseConnector

SUPPORTED_CONNECTOR_TYPES = (
    "web",
    "s3",
    "fileshare",
    "sql",
    "confluence",
    "rest",
    "salesforce",
    "sharepoint",
)


def build_connector(connector_type: str, config: dict[str, Any]) -> BaseConnector:
    """Instantiate a connector by type.

    Raises:
        ValueError: if the connector type is not supported.
    """
    kind = connector_type.lower()

    if kind == "web":
        from app.domain.connectors.web import WebConnector

        return WebConnector(config)
    if kind == "s3":
        from app.domain.connectors.s3_connector import S3BucketConnector

        return S3BucketConnector(config)
    if kind == "fileshare":
        from app.domain.connectors.local_fileshare import LocalFileShareConnector

        return LocalFileShareConnector(config)
    if kind == "sql":
        from app.domain.connectors.sql_connector import SqlConnector

        return SqlConnector(config)
    if kind == "confluence":
        from app.domain.connectors.confluence import ConfluenceConnector

        return ConfluenceConnector(config)
    if kind == "rest":
        from app.domain.connectors.generic_rest import RestApiConnector

        return RestApiConnector(config)
    if kind == "salesforce":
        from app.domain.connectors.salesforce import SalesforceConnector

        return SalesforceConnector(config)
    if kind == "sharepoint":
        from app.domain.connectors.sharepoint import SharePointConnector

        return SharePointConnector(config)

    raise ValueError(f"Unsupported connector type: {connector_type}")
