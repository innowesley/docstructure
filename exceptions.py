"""DocStructure exceptions — typed error hierarchy."""


class DocStructureError(Exception):
    """Base for all docstructure errors."""


class UnsupportedFormatError(DocStructureError):
    """Input format is not supported."""


class ParseError(DocStructureError):
    """File could not be parsed."""
