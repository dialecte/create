"""Extract documentation string from an XSD element."""
from typing import Any
def extract_docs(xsd_elem: Any) -> str | None:
    """Extract the first xs:documentation text from an XSD element's annotations.

    xmlschema API:
      XsdElement.annotation → XsdAnnotation | None
      XsdAnnotation.documentation → list[XsdDocumentation]
      XsdDocumentation.text → str
    """
    # Try .annotation (singular) first — xmlschema v2+
    annotation = getattr(xsd_elem, 'annotation', None)
    if annotation is not None:
        docs = getattr(annotation, 'documentation', None)
        if docs:
            for doc in docs:
                text = getattr(doc, 'text', None)
                if text and text.strip():
                    return text.strip()

    # Fallback: .annotations (plural) — older xmlschema
    annotations = getattr(xsd_elem, 'annotations', None)
    if annotations:
        for ann in annotations:
            docs = getattr(ann, 'documentation', None)
            if docs:
                for doc in docs:
                    text = getattr(doc, 'text', None)
                    if text and text.strip():
                        return text.strip()

    return None
