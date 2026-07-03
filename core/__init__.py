"""DocStructure core — document graph data model."""

from docstructure.core.analysis import Diagnostic, DocumentAnalysis, Location, ReferenceEntry
from docstructure.core.common import (
    EdgeType,
    ParagraphRole,
    Provenance,
    RegionType,
    Severity,
    Signal,
)
from docstructure.core.document import Document
from docstructure.core.nodes import (
    BlockFeatures,
    BlockNode,
    CodeBlock,
    Edge,
    EquationBlock,
    FigureBlock,
    GraphNode,
    ListBlock,
    ListItem,
    PageBreak,
    ParagraphBlock,
    RegionNode,
    Run,
    SectionBreak,
    TableBlock,
    TableCell,
    TableRow,
)
