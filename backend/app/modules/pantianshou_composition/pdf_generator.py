from __future__ import annotations

from typing import List


def _pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_simple_pdf(title: str, lines: List[str]) -> bytes:
    y = 760
    content_parts = [
        "BT",
        "/F1 18 Tf",
        f"72 {y} Td",
        f"({_pdf_escape(title)}) Tj",
        "ET",
    ]
    y -= 36
    for line in lines:
        content_parts.extend(
            [
                "BT",
                "/F1 12 Tf",
                f"72 {y} Td",
                f"({_pdf_escape(line)}) Tj",
                "ET",
            ]
        )
        y -= 18
        if y < 72:
            break

    content = "\n".join(content_parts).encode("utf-8")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    for obj in objects:
        offsets.append(len(header) + len(body))
        body += obj

    xref_start = len(header) + len(body)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("ascii"))
    xref_bytes = b"".join(xref)
    trailer = b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_start).encode("ascii") + b"\n%%EOF\n"
    return header + body + xref_bytes + trailer

