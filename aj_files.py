import os
from pathlib import Path


ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".csv",
    ".xml",
    ".java",
    ".c",
    ".cpp",
    ".sql",
    ".pdf",
}


def is_supported_file(filename):
    """
    Check whether AJ supports the uploaded file type.
    """

    extension = Path(filename).suffix.lower()

    return extension in ALLOWED_EXTENSIONS


def read_text_file(file_path):
    """
    Read normal text/code files.
    """

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        return file.read()


def read_pdf_file(file_path):
    """
    Extract text from a PDF.
    """

    try:

        from pypdf import PdfReader

        reader = PdfReader(file_path)

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n\n".join(pages)

    except Exception as error:

        print(
            "PDF READ ERROR:",
            error
        )

        return ""


def read_file(file_path):
    """
    Read a supported file and return its text.
    """

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":

        return read_pdf_file(file_path)

    return read_text_file(file_path)


def get_file_info(file_path):
    """
    Return basic information about a file.
    """

    path = Path(file_path)

    if not path.exists():

        return {
            "name": path.name,
            "exists": False,
            "size": 0,
            "extension": path.suffix.lower()
        }

    return {
        "name": path.name,
        "exists": True,
        "size": path.stat().st_size,
        "extension": path.suffix.lower()
    }


def prepare_file_for_ai(
    file_path,
    max_characters=50000
):
    """
    Prepare a file's contents for AJ's AI brain.
    """

    info = get_file_info(file_path)

    if not info["exists"]:

        return {
            "success": False,
            "error": "File not found."
        }

    if not is_supported_file(info["name"]):

        return {
            "success": False,
            "error": (
                f"AJ does not support "
                f"{info['extension']} files yet."
            )
        }

    try:

        content = read_file(file_path)

        if not content:

            return {
                "success": False,
                "error": (
                    "AJ could not extract "
                    "text from this file."
                )
            }

        truncated = False

        if len(content) > max_characters:

            content = content[:max_characters]

            truncated = True

        return {
            "success": True,
            "name": info["name"],
            "extension": info["extension"],
            "size": info["size"],
            "content": content,
            "truncated": truncated
        }

    except Exception as error:

        print(
            "FILE INTELLIGENCE ERROR:",
            error
        )

        return {
            "success": False,
            "error": (
                "AJ could not read "
                "this file."
            )
        }
