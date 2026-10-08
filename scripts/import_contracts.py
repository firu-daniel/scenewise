"""Custom import-linter contract: an allow-list for third-party imports."""

import sys
from typing import TYPE_CHECKING, cast, override

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output

if TYPE_CHECKING:
    from importlinter.domain.imports import Module


class AllowedExternalsContract(Contract):
    """Modules in ``source_modules`` import only stdlib, the root and ``allowed``."""

    source_modules = fields.ListField(subfield=fields.ModuleField())
    allowed = fields.ListField(
        subfield=fields.StringField(), required=False, default=[]
    )

    @override
    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        """Collect every import of a non-allowed external top-level package."""
        del verbose
        roots = set(self.session_options["root_packages"])
        extra = cast("list[str]", self.allowed)
        permitted = set(sys.stdlib_module_names) | roots | {"__future__", *extra}
        bad: list[tuple[str, str, int]] = []
        for source in cast("list[Module]", self.source_modules):
            name = source.name
            for importer in sorted({name} | graph.find_descendants(name)):
                imported_by = graph.find_modules_directly_imported_by(importer)
                for imported in sorted(imported_by):
                    if imported.split(".")[0] in permitted:
                        continue
                    details = graph.get_import_details(
                        importer=importer, imported=imported
                    )
                    bad += [(importer, imported, d["line_number"]) for d in details]
        return ContractCheck(kept=not bad, metadata={"bad": bad})

    @override
    def render_broken_contract(self, check: ContractCheck) -> None:
        """Print one line per forbidden import."""
        for importer, imported, line in check.metadata["bad"]:
            output.print_error(
                f"{importer} -> {imported} (l.{line}) is not on the allow-list"
            )
