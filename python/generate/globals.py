"""Inject explicitly mapped global attributes from the schema into target elements.

Reads ``attribute-mapping.json`` from the same directory as the entry XSD.
Format::

    {
      "ElementName": {
        "prefix:localName": "namespace-uri",
        ...
      }
    }

The key ``prefix:localName`` becomes the attribute key in ``attr_sequence`` and
``attributes``. The namespace URI is used to look up the global ``xs:attribute``
declaration in ``schema.maps.attributes`` via Clark notation ``{uri}localName``.

No heuristics — only explicitly declared mappings are injected.
Pattern mirrors ``orphans.py``.
"""
import json
from pathlib import Path
from typing import Any

from generate.extractors.facets import extract_facets
from generate.extractors.namespace import extract_attr_namespace
from generate.ir import AttributeDef, ElementDef


def load_attr_mapping(entry_path: Path) -> dict[str, dict[str, str]]:
    """Read attribute-mapping.json from the same directory as the entry XSD.

    Returns empty dict if the file does not exist.
    """
    mapping_file = entry_path.parent / 'attribute-mapping.json'
    if not mapping_file.exists():
        return {}
    with open(mapping_file) as f:
        return json.load(f)


def inject_mapped_attributes(
    schema: Any,
    elements: dict[str, ElementDef],
    mapping: dict[str, dict[str, str]],
) -> int:
    """Inject global attributes into elements as declared in the mapping.

    For each ``(element_name, attr_key, ns_uri)`` in the mapping:
    - Looks up the global attr in ``schema.maps.attributes`` by Clark name ``{ns_uri}local``.
    - Builds an ``AttributeDef`` from the global attr declaration.
    - Injects into ``element.attributes[attr_key]`` and ``element.attr_sequence``.
    - Idempotent: skips if key already present.

    Returns total number of attributes injected.
    """
    maps = getattr(schema, 'maps', None)
    global_attrs = getattr(maps, 'attributes', None) if maps else {}

    injected = 0

    for element_name, attr_entries in mapping.items():
        elem = elements.get(element_name)
        if elem is None:
            continue

        for key, ns_uri in attr_entries.items():
            if key in elem.attributes:
                continue  # already present

            # Derive local name from key (strip prefix if present)
            local = key.split(':', 1)[-1]
            clark = f'{{{ns_uri}}}{local}'
            xsd_attr = global_attrs.get(clark)
            if xsd_attr is None:
                continue  # not found in schema — skip silently

            attr_ns = extract_attr_namespace(xsd_attr)
            fixed = getattr(xsd_attr, 'fixed', None)
            default = getattr(xsd_attr, 'default', None) if fixed is None else None
            use = getattr(xsd_attr, 'use', 'optional')
            attr_type = getattr(xsd_attr, 'type', None)

            elem.attributes[key] = AttributeDef(
                required=use == 'required',
                default=default,
                fixed=fixed,
                namespace=attr_ns,
                facets=extract_facets(attr_type),
            )
            elem.attr_sequence.append(key)
            injected += 1

        if any(k in elem.attr_sequence for k in attr_entries):
            elem.attr_sequence.sort()

    return injected


    return injected
