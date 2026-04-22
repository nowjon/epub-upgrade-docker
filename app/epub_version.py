"""Read EPUB package version from the OPF inside the container ZIP."""

from __future__ import annotations

import re
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


NS_CONTAINER = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
}
def _major_from_version_attr(value: str | None) -> int | None:
    if not value:
        return None
    m = re.match(r"^\s*(\d+)", value.strip())
    if not m:
        return None
    return int(m.group(1))


def read_opf_major_version(epub_path: Path) -> int | None:
    """
    Return the major OPF version (2 for EPUB 2, 3 for EPUB 3) or None if unknown.
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            try:
                raw_container = zf.read("META-INF/container.xml")
            except KeyError:
                return None

            croot = ET.fromstring(raw_container)
            opf_rel = None
            for el in croot.findall(".//c:rootfile", NS_CONTAINER):
                opf_rel = el.get("full-path")
                if opf_rel:
                    break
            if not opf_rel:
                for el in croot.iter():
                    if el.tag.endswith("rootfile"):
                        opf_rel = el.get("full-path")
                        if opf_rel:
                            break
            if not opf_rel:
                return None

            try:
                raw_opf = zf.read(opf_rel)
            except KeyError:
                return None
    except (zipfile.BadZipFile, OSError):
        return None

    oroot = ET.fromstring(raw_opf)
    version = oroot.get("version")
    major = _major_from_version_attr(version)
    if major is not None:
        return major

    # Fallback: unprefixed tag name
    if oroot.tag.endswith("package"):
        return _major_from_version_attr(oroot.get("version"))

    return None


def is_epub2(epub_path: Path) -> bool:
    major = read_opf_major_version(epub_path)
    if major is None:
        return False
    return major < 3
