"""Module for gradio interfaces."""

import os
from pathlib import Path
import gradio as gr

from translator.content import (
    fill_scaffold,
    get_content,
    get_full_prompt,
    llm_translate,
    preprocess_content,
)
from translator.retriever import report, get_github_issue_open_pr
from pr_generator.agent import GitHubPRAgent


def report_translation_target_files(
    translate_lang: str, top_k: int = 1
) -> tuple[str, list[list[str]]]:
    """Return the top-k files that need translation, excluding files already in progress.

    Args:
        translate_lang: Target language to translate
        top_k: Number of top-first files to return for translation. (Default 1)
    """
    # Get files in progress
    docs_in_progress, pr_info_list = get_github_issue_open_pr(translate_lang)

    # Get all available files for translation
    all_status_report, all_filepath_list = report(translate_lang, top_k * 2)  # Get more to account for filtering

    # Filter out files that are already in progress
    available_files = [f for f in all_filepath_list if f not in docs_in_progress]

    # Take only the requested number
    filepath_list = available_files[:top_k]
    
    # Build combined status report
    status_report = all_status_report

    if docs_in_progress:
        status_report += f"\n\n🤖 Found {len(docs_in_progress)} files in progress for translation:"
        for i, file in enumerate(docs_in_progress):
            status_report += f"\n{i+1}. `{file}`: {pr_info_list[i]}"
        status_report += f"\n\n📋 Showing {len(filepath_list)} available files (excluding in-progress):"

    return status_report, [[file] for file in filepath_list]


def translate_docs(lang: str, file_path: str, additional_instruction: str = "") -> tuple[str, str]:
    """Translate documentation."""
    # Check if translation already exists
    translation_file_path = (
        Path(__file__).resolve().parent.parent
        / f"translation_result/{file_path}"
    )

    if translation_file_path.exists():
        print(f"📄 Found existing translation: {translation_file_path}")
        with open(translation_file_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
        if existing_content.strip():
            return "Existing translation loaded (no tokens used)", existing_content

    # step 1. Get content from file path
    content = get_content(file_path)
    to_translate = preprocess_content(content)

    # step 2. Prepare prompt with docs content
    if lang == "ko":
        translation_lang = "Korean"
    to_translate_with_prompt = get_full_prompt(translation_lang, to_translate, additional_instruction)

    print("to_translate_with_prompt:\n", to_translate_with_prompt)

    # step 3. Translate with LLM
    # TODO: MCP clilent 넘길 부분
    callback_result, translated_content = llm_translate(to_translate_with_prompt)
    print("translated_content:\n")
    print(translated_content)
    # step 4. Add scaffold to translation result
    translated_doc = fill_scaffold(content, to_translate, translated_content)
    print("translated_doc:\n")
    print(translated_doc)
    return callback_result, translated_doc


def translate_docs_interactive(
    translate_lang: str, selected_files: list[list[str]], additional_instruction: str = ""
) -> tuple[str, str]:
    """Interactive translation function that processes files one by one.

    Args:
        translate_lang: Target language to translate
        selected_files: List of file paths to translate
    """
    # Extract file paths from the dataframe format
    file_paths = [row[0] for row in selected_files if row and len(row) > 0]

    # Start with the first file
    current_file = file_paths[0]

    status = f"✅ Translation completed: `{current_file}` → `{translate_lang}`\n\n"
    callback_result, translated_content = translate_docs(translate_lang, current_file, additional_instruction)
    status += f"💰 Used token and cost: \n```\n{callback_result}\n```"

    print(status)

    return translated_content


def generate_github_pr(
    target_language: str,
    filepath: str,
    translated_content: str = None,
    github_config: dict = None,
    en_title: str = None,
) -> str:
    """Generate a GitHub PR for translated documentation.

    Args:
        target_language: Target language for translation (e.g., "ko")
        filepath: Original file path (e.g., "docs/source/en/accelerator_selection.md")
        translated_content: Translated content (if None, read from file)
        github_config: GitHub configuration dictionary
        en_title: English title for toctree mapping

    Returns:
        PR creation result message
    """
    if not GITHUB_PR_AVAILABLE:
        return "❌ GitHub PR Agent is not available. Please install required libraries."

    if not github_config:
        return "❌ GitHub configuration not provided."

    # Validate required configuration
    required_fields = ["token", "owner", "repo_name", "reference_pr_url"]
    missing_fields = [
        field for field in required_fields if not github_config.get(field)
    ]

    if missing_fields:
        return f"❌ Missing required configuration: {', '.join(missing_fields)}. Please provide these values."

    # Set token in environment for the agent.
    os.environ["GITHUB_TOKEN"] = github_config["token"]

    try:
        # Read translated content from file if not provided
        if translated_content is None:
            translation_file_path = (
                Path(__file__).resolve().parent.parent
                / f"translation_result/{filepath}"
            )
            if not translation_file_path.exists():
                return f"❌ Translation file not found: {translation_file_path}"

            with open(translation_file_path, "r", encoding="utf-8") as f:
                translated_content = f.read()

        if not translated_content or not translated_content.strip():
            return "❌ Translated content is empty."

        # Execute GitHub PR Agent
        print(f"🚀 Starting GitHub PR creation...")
        print(f"   📁 File: {filepath}")
        print(f"   🌍 Language: {target_language}")
        print(f"   📊 Reference PR: {github_config['reference_pr_url']}")
        print(f"   🏠 Repository: {github_config['owner']}/{github_config['repo_name']}")

        agent = GitHubPRAgent()
        # result = agent.run_translation_pr_workflow(
        #     reference_pr_url=github_config["reference_pr_url"],
        #     target_language=target_language,
        #     filepath=filepath,
        #     translated_doc=translated_content,
        #     owner=github_config["owner"],
        #     repo_name=github_config["repo_name"],
        #     base_branch=github_config.get("base_branch", "main"),
        # )
        result = {
            'status': 'partial_success', 
            'branch': 'ko-attention_interface', 
            'file_path': 'docs/source/ko/attention_interface.md', 
            'message': 'File was saved and commit was successful.\nPR creation failed: ERROR: Existing PR found: https://github.com/Jwaminju/transformers/pull/1', 'error_details': 'ERROR: Existing PR found: https://github.com/Jwaminju/transformers/pull/1'
            }
        # Process toctree update after successful translation PR
        toctree_result = None
        if en_title:
            from agent.toctree_handler import TocTreeHandler
            toctree_handler = TocTreeHandler()
            toctree_result = toctree_handler.update_toctree_after_translation(
                result, filepath, agent, github_config
            )

        # Process result
        # Generate toctree status message (shared for both success and partial_success)
        toctree_status = ""
        if toctree_result:
            if toctree_result["status"] == "success":
                toctree_status = f"\n📋 **Toctree Updated:** ✅ {toctree_result['message']}"
            else:
                toctree_status = f"\n📋 **Toctree Update Failed:** ❌ {toctree_result['message']}"

        # Append full result JSON to GitHub log file (always, env-configured repo/branch/path)
        try:
            import json
            log_entry = json.dumps(result, ensure_ascii=False) + "\n"
            log_res = agent.append_to_log_file(log_entry=log_entry)
            print(f"📝 Log append result: {log_res}")
        except Exception as e:
            print(f"❌ Failed to append PR log via GitHub API: {e}")

        if result["status"] == "success":
            return f"""✅ **GitHub PR Creation Successful!**

🔗 **PR URL:** {result.get('pr_url', 'NO_PR_URL')}
🌿 **Branch:** {result["branch"]}
📁 **File:** {result["file_path"]}{toctree_status}

{result["message"]}"""

        elif result["status"] == "partial_success":
            return f"""⚠️ **Partial Success**

🌿 **Branch:** {result["branch"]}
📁 **File:** {result["file_path"]}{toctree_status}

{result["message"]}

**Error Details:**
{result.get("error_details", "Unknown error")}"""

        else:
            return f"""❌ **GitHub PR Creation Failed**

**Error Message:**
{result["message"]}"""

    except Exception as e:
        error_msg = f"❌ Unexpected error occurred during PR creation: {str(e)}"
        print(error_msg)
        return error_msg


# Backward compatibility function (replaces old mock function)
def mock_generate_PR():
    """Backward compatibility function - returns warning message only"""
    return (
        "⚠️ mock_generate_PR() is deprecated. Please use generate_github_pr() instead."
    )
