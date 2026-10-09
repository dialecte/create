"""What the generator refuses, by name: it never writes a definition it cannot stand behind."""


class SchemaNotReadable(Exception):
    """A document of the schema could not be read where it is (never fetched from the network)."""


class SchemaNotRepresentable(Exception):
    """The schema declares something the definition cannot write faithfully."""


class SidecarMistake(Exception):
    """A sidecar file next to the entry document names what the schema does not declare."""
