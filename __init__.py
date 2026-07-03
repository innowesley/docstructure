"""DocStructure — document structure analysis engine.

Usage:
    from docstructure import analyze
    doc = analyze("paper.docx")
    doc.to_json("output.json")
"""

from docstructure.pipeline import run_pipeline as analyze
from docstructure.output.json import to_json, to_file, serialize

__version__ = "0.1.0"
