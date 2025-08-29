import re
import os
from pathlib import Path

import requests

from .model import Languages, Summary, TranslationDoc
from .project_config import get_project_config


def get_github_repo_files(project: str = "transformers"):
    """
    Get github repo files
    """
    config = get_project_config(project)
    
    # Add GitHub token if available to avoid rate limiting
    headers = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    response = requests.get(config.api_url, headers=headers)

    data = response.json()
    all_items = data.get("tree", [])

    file_paths = [
        item["path"]
        for item in all_items
        if item["type"] == "blob" and (item["path"].startswith("docs"))
    ]
    return file_paths


def get_github_issue_open_pr(project: str = "transformers", lang: str = "ko"):
    """
    Get open PR in the github issue, filtered by title containing '[i18n-KO]'.
    """
    config = get_project_config(project)
    issue_id = config.github_issues.get(lang)
    
    # For projects without GitHub issue tracking, still search for PRs
    if not issue_id:
        raise ValueError(f"⚠️ No GitHub issue registered for {project}.")

    headers = {
        "Accept": "application/vnd.github+json",
    }
    
    # Add GitHub token if available to avoid rate limiting
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    all_open_prs = []
    page = 1
    per_page = 100  # Maximum allowed by GitHub API
    
    while True:
        repo_path = config.repo_url.replace("https://github.com/", "")
        url = f"https://api.github.com/repos/{repo_path}/pulls?state=open&page={page}&per_page={per_page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} {response.text}")
        
        page_prs = response.json()
        if not page_prs:  # No more PRs
            break
            
        all_open_prs.extend(page_prs)
        page += 1
        
        # Break if we got less than per_page results (last page)
        if len(page_prs) < per_page:
            break

    filtered_prs = [pr for pr in all_open_prs if "[i18n-KO]" in pr["title"]]

    # Pattern to match both `filename.md` and filename.md formats
    pattern = re.compile(r"(?:`([^`]+\.md)`|(\w+\.md))")

    filenames = []
    for pr in filtered_prs:
        match = pattern.search(pr["title"])
        if match:
            # Use group 1 (with backticks) or group 2 (without backticks)
            filename = match.group(1) or match.group(2)
            filenames.append("docs/source/en/" + filename)
    pr_info_list = [
        f"{config.repo_url}/pull/{pr['url'].rstrip('/').split('/')[-1]}"
        for pr in filtered_prs
    ]
    return filenames, pr_info_list


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


def report(project: str, target_lang: str, top_k: int = 1) -> tuple[str, list[str]]:
    """
    Generate a report for the translated docs
    """
    docs_file = get_github_repo_files(project)

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
