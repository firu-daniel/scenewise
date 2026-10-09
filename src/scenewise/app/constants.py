"""Use-case and wire-contract constants shared by more than one module."""

from typing import Final, Literal

# Every v1 wire document carries ``schema_version: "1"``. ``Literal[...]`` cannot name a
# ``Final`` (PEP 586), so the models use the alias and stamp the constant.
type SchemaVersionV1 = Literal["1"]
SCHEMA_VERSION_V1: Final[SchemaVersionV1] = "1"

JSON_MEDIA_TYPE: Final = "application/json"
