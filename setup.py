from setuptools import setup

setup(
    package_dir={
        "docstructure": ".",
        "docstructure.classifier": "classifier",
        "docstructure.core": "core",
        "docstructure.features": "features",
        "docstructure.formats": "formats",
        "docstructure.graph": "graph",
        "docstructure.normalizer": "normalizer",
        "docstructure.output": "output",
        "docstructure.output.schema": "output/schema",
        "docstructure.parser": "parser",
        "docstructure.validate": "validate",
        "docstructure.validate.rules": "validate/rules",
    },
    packages=[
        "docstructure",
        "docstructure.classifier",
        "docstructure.core",
        "docstructure.features",
        "docstructure.formats",
        "docstructure.graph",
        "docstructure.normalizer",
        "docstructure.output",
        "docstructure.output.schema",
        "docstructure.parser",
        "docstructure.validate",
        "docstructure.validate.rules",
    ],
    package_data={
        "docstructure": ["output/schema/*.json"],
    },
)
