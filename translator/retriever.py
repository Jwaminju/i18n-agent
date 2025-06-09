import os
from pathlib import Path

import requests

from .model import Languages, Summary, TranslationDoc

URL = "https://api.github.com/repos/huggingface/transformers/git/trees/main?recursive=1"


def get_github_repo_files():
    """
    Get github repo files
    """
    response = requests.get(URL)

    data = response.json()
    all_items = data.get("tree", [])

    file_paths = [
        item["path"]
        for item in all_items
        if item["type"] == "blob" and (item["path"].startswith("docs"))
    ]
    return file_paths


def retrieve(summary: Summary, table_size: int = 10) -> tuple[str, list[str]]:
    """
    Retrieve missing docs
    """

    report = f"""
| Item | Count | Percentage |
|------|-------|------------|
| 📂 HuggingFaces docs | {summary.files_analyzed} | - |
| 🪹 Missing translations | {summary.files_missing_translation} | {summary.percentage_missing_translation:.2f}% |
"""
    print(report)
    first_missing_docs = list()
    for file in summary.first_missing_translation_files(table_size):
        first_missing_docs.append(file.original_file)

    print(first_missing_docs)
    return report, first_missing_docs


def report(target_lang: str, top_k: int = 1) -> tuple[str, list[str]]:
    """
    Generate a report for the translated docs
    """
    docs_file = get_github_repo_files()

    base_docs_path = Path("docs/source")
    en_docs_path = Path("docs/source/en")

    lang = Languages[target_lang]
    summary = Summary(lang=lang.value)

    for file in docs_file:
        if file.endswith(".md"):
            try:
                file_relative_path = Path(file).relative_to(en_docs_path)
            except ValueError:
                continue

            translated_path = os.path.join(
                base_docs_path, lang.value, file_relative_path
            )
            translation_exists = translated_path in docs_file

            doc = TranslationDoc(
                translation_lang=lang.value,
                original_file=file,
                translation_file=translated_path,
                translation_exists=translation_exists,
            )
            summary.append_file(doc)
    return retrieve(summary, top_k)
