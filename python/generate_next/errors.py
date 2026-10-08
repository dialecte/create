"""What the generator refuses, by name: it never writes a definition it cannot stand behind."""


class SchemaNotReadable(Exception):
    """A document of the schema could not be read where it is (never fetched from the network)."""


class SchemaNotRepresentable(Exception):
    """The schema declares something the definition cannot write faithfully."""
