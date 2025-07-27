"""Module for gradio chat-based translation agent interface."""

import os
import re
from pathlib import Path

import gradio as gr

from agent.workflow import (
    report_translation_target_files,
    report_in_translation_status_files,
    translate_docs_interactive,
    generate_github_pr,
)
from pr_generator.searcher import find_reference_pr_simple_stream
from translator.content import get_full_prompt, get_content, preprocess_content


# State management
class ChatState:
    def __init__(self):
        self.step = "welcome"  # welcome -> find_files -> translate -> create_github_pr
        self.target_language = "ko"
        self.k_files = 10
        self.files_to_translate = []
        self.additional_instruction = ""
        self.current_file_content = {"translated": ""}
        self.pr_result = None  # Store PR creation result
        # GitHub configuration
        self.github_config = {
            "token": "",
            "owner": "",
            "repo_name": "",
            "reference_pr_url": "https://github.com/huggingface/transformers/pull/24968",
        }


state = ChatState()


def _extract_content_for_display(content: str) -> str:
    """Extract text from document for display."""
    # Remove Copyright header
    to_translate = re.sub(r"<!--.*?-->", "", content, count=1, flags=re.DOTALL)
    to_translate = to_translate.strip()
    ## remove code blocks from text
    to_translate = re.sub(r"```.*?```", "", to_translate, flags=re.DOTALL)
    ## remove markdown tables from text
    to_translate = re.sub(r"^\|.*\|$\n?", "", to_translate, flags=re.MULTILINE)
    ## remove empty lines from text
    to_translate = re.sub(r"\n\n+", "\n\n", to_translate)

    return to_translate


def get_welcome_message():
    """Initial welcome message with file finding controls"""
    return """**👋 Welcome to 🌐 Hugging Face i18n Translation Agent!**

I'll help you find files that need translation and translate them in a streamlined workflow.

**🔎 Let's start by finding files that need translation.**

Use the **`Quick Controls`** on the right or **ask me `what`, `how`, or `help`** to get started.
"""


def process_file_search_handler(lang: str, k: int, history: list) -> tuple:
    """Process file search request and update Gradio UI components."""
    global state
    state.target_language = lang
    state.k_files = k
    state.step = "find_files"

    status_report, files_list = report_translation_target_files(lang, k)
    in_progress_status_report, in_progress_docs = report_in_translation_status_files(
        lang
    )
    state.files_to_translate = (
        [file[0] for file in files_list if file[0] not in in_progress_docs]
        if files_list
        else []
    )

    response = f"""**✅ File search completed!**

**Status Report:**
{status_report}
{in_progress_status_report}
**📁 Found first {len(state.files_to_translate)} files to translate:**
"""

    if state.files_to_translate:
        for i, file in enumerate(state.files_to_translate, 1):
            response += f"\n{i}. `{file}`"

        # if len(state.files_to_translate) > 5:
        #     response += f"\n... and {len(state.files_to_translate) - 5} more files"

        response += "\n\n**🚀 Ready to start translation?**\nI can begin translating these files one by one. Would you like to proceed?"
    else:
        response += "\nNo files found that need translation."

    # Add to history
    history.append(["Please find files that need translation", response])
    cleared_input = ""
    selected_tab = 1 if state.files_to_translate else 0

    # 드롭다운 choices로 쓸 파일 리스트 반환 추가
    return (
        history,
        cleared_input,
        update_status(),
        gr.Tabs(selected=selected_tab),
        update_dropdown_choices(state.files_to_translate),
    )


def update_dropdown_choices(file_list):
    return gr.update(choices=file_list, value=None)


def start_translation_process():
    """Start the translation process for the first file"""
    if not state.files_to_translate:
        return "❌ No files available for translation."

    current_file = state.files_to_translate[0]

    # Call translation function (simplified for demo)
    try:
        translated = translate_docs_interactive(
            state.target_language, [[current_file]], state.additional_instruction
        )

        state.current_file_content = {"translated": translated}
        path = (
            Path(__file__).resolve().parent.parent
            / f"translation_result/{current_file}"
        )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(translated, encoding="utf-8")

        original_file_link = (
            "https://github.com/huggingface/transformers/blob/main/" + current_file
        )
        print("Compeleted translation:\n")
        print(translated)
        print("----------------------------")
        response = (
            f"""🔄 Translation for: `{current_file}`\n"""
            "**📄 Original Content Link:**\n"
            ""
            f"{original_file_link}\n"
            "**🌐 Translated Content:**\n"
            # f"\n```\n\n{_extract_content_for_display(translated)}\n```"
            # "\n```\n\n"
            # f"\n{translated}\n"
            # f"```"
            # f"{status}\n"
            # "✅ Translation completed. The code block will be added when generating PR."
        )
        return response, translated


    except Exception as e:
        response = f"❌ Translation failed: {str(e)}"
        response += "\n**➡️ Please try from the beginning.**"

    return response


def handle_general_message(message):
    """Handle general messages"""
    message_lower = message.lower()

    if any(word in message_lower for word in ["help", "what", "how"]):
        return """**🤖 I'm your Hugging Face i18n Translation Agent!**

I can help you:
1. **🔍 Find files** that need translation
2. **🌐 Translate documents** using AI
3. **📋 Review translations** for quality
4. **🚀 Create GitHub PR** for translation

Currently available actions with quick controls:
- "find files" - Search for files needing translation
- "translate" - Start translation process  
- "review" - Review current translation
- "github" - Create GitHub Pull Request
- "restart" - Start over"""

    elif "restart" in message_lower:
        global state
        state = ChatState()
        return get_welcome_message()

    else:
        return """I understand you want to work on translations! 

To get started, please use the controls above to configure your translation settings and find files that need translation.
"""


# Main handler
def handle_user_message(message, history):
    """Handle user messages and provide appropriate responses"""
    global state

    if not message.strip():
        return history, ""

    elif state.step == "find_files" and any(
        word in message.lower()
        for word in ["yes", "proceed", "start", "translate", "translation"]
    ):
        # User wants to start translation
        if state.files_to_translate:
            state.step = "translate"
            response, translated = start_translation_process()
            history.append([message, response])
            history.append(["", translated])
            return history, ""
        else:
            response = (
                "❌ No files available for translation. Please search for files first."
            )
    # Handle GitHub PR creation - This part is removed as approve_handler is the main entry point
    else:
        # General response
        response = handle_general_message(message)

    history.append([message, response])
    return history, ""


def update_status():
    if state.step == "welcome":
        return """
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;padding: 10px; background: rgba(0, 0, 0, 0.25); border-radius: 8px;">
            <div><strong>🔄 Step:</strong> Welcome</div>
            <div><strong>📁 Files:</strong> 0</div>
            <div><strong>🌍 Language:</strong> ko</div>
            <div><strong>⏳ Progress:</strong> Ready</div>
        </div>
        """

    step_map = {
        "welcome": "Welcome",
        "find_files": "Finding Files",
        "translate": "Translating",
        "review": "Reviewing",
        "create_github_pr": "Creating PR",
    }

    progress_map = {
        "welcome": "Ready to start",
        "find_files": "Files found",
        "translate": f"{len(state.files_to_translate)} remaining",
        "review": "Review complete",
        "create_github_pr": "PR generation in progress",
    }

    # Check GitHub configuration status
    github_status = "❌ Not configured"
    if all(
        [
            state.github_config["token"],
            state.github_config["owner"],
            state.github_config["repo_name"],
        ]
    ):
        github_status = (
            f"✅ {state.github_config['owner']}/{state.github_config['repo_name']}"
        )

    status_html = f"""
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px; background: rgba(0, 0, 0, 0.25); border-radius: 8px;">
        <div><strong>🔄 Step:</strong> {step_map.get(state.step, state.step)}</div>
        <div><strong>📁 Files:</strong> {len(state.files_to_translate)}</div>
        <div><strong>🌍 Language:</strong> {state.target_language}</div>
        <div><strong>⏳ Progress:</strong> {progress_map.get(state.step, 'In progress')}</div>
        <div><strong>🔧 GitHub:</strong> {github_status}</div>
    </div>
    """

    return status_html


# Event handlers


def sync_language_displays(lang):
    return lang


def update_github_config(token, owner, repo, reference_pr_url):
    """Update GitHub configuration settings."""
    global state

    # Set GitHub token in environment variables
    if token:
        os.environ["GITHUB_TOKEN"] = token

    # Save GitHub configuration to state
    state.github_config.update(
        {
            "token": token,
            "owner": owner,
            "repo_name": repo,
            "reference_pr_url": reference_pr_url
            or state.github_config["reference_pr_url"],
        }
    )

    return f"✅ GitHub configuration updated: {owner}/{repo}"


def update_prompt_preview(language, file_path, additional_instruction):
    """Update prompt preview based on current settings"""
    if not file_path.strip():
        return "Select a file to see the prompt preview..."
    
    try:
        # Get language name
        if language == "ko":
            translation_lang = "Korean"
        else:
            translation_lang = language
        
        # Get sample content (first 500 characters)
        content = get_content(file_path)
        to_translate = preprocess_content(content)
        
        # Truncate for preview
        sample_content = to_translate[:500] + ("..." if len(to_translate) > 500 else "")
        
        # Generate prompt
        prompt = get_full_prompt(translation_lang, sample_content, additional_instruction)
        
        return prompt
    except Exception as e:
        return f"Error generating prompt preview: {str(e)}"


def send_message(message, history):
    new_history, cleared_input = handle_user_message(message, history)
    return new_history, cleared_input, update_status()


# Button handlers with tab switching
def start_translate_handler(history, anthropic_key, file_to_translate, additional_instruction=""):
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    
    state.additional_instruction = additional_instruction
    state.files_to_translate = [file_to_translate]
    new_hist, cleared_input = handle_user_message("start translation", history)
    selected_tabs = 2 if state.current_file_content["translated"] else 0
    return new_hist, cleared_input, update_status(), gr.Tabs(selected=selected_tabs)


def approve_handler(history, owner, repo, reference_pr_url):
    """Handles the request to generate a GitHub PR."""
    global state
    state.step = "create_github_pr"

    # Update github config from the latest UI values
    state.github_config["owner"] = owner
    state.github_config["repo_name"] = repo
    state.github_config["reference_pr_url"] = reference_pr_url

    # Validate GitHub configuration
    github_config = state.github_config
    if not all([github_config.get("token"), owner, repo]):
        response = "❌ GitHub configuration incomplete. Please provide GitHub Token, Owner, and Repository Name in Tab 3."
        history.append(["GitHub PR creation request", response])
        return history, "", update_status()

    # If reference PR is not provided, use the agent to find one
    if not github_config.get("reference_pr_url"):
        response = "🤖 **Reference PR URL not found. The agent will now search for a suitable one...**"
        try:
            # This part is simplified to avoid streaming logic in a non-generator function
            stream_gen = find_reference_pr_simple_stream(
                target_language=state.target_language,
                context="documentation translation",
            )
            # We will just get the final result from the generator
            final_result = None
            try:
                while True:
                    # We are not interested in the streamed messages here, just the final result.
                    next(stream_gen)
            except StopIteration as e:
                final_result = e.value

            if final_result and final_result.get("status") == "success":
                result_text = final_result.get("result", "")
                match = re.search(r"https://github.com/[^\s]+", result_text)
                if match:
                    found_url = match.group(0)
                    state.github_config["reference_pr_url"] = found_url
                    response += f"\n✅ **Agent found a reference PR:** {found_url}"
                else:
                    raise ValueError(
                        "Could not extract a valid PR URL from agent's response."
                    )
            else:
                error_message = final_result.get("message") or final_result.get(
                    "result", "Unknown error"
                )
                raise ValueError(f"Agent failed to find a PR. Reason: {error_message}")
        except Exception as e:
            response += f"\n❌ **Agent failed to find a reference PR.**\nReason: {e}\n\nPlease provide a reference PR URL manually in Tab 3 and try again."
            history.append(["Agent searching for PR", response])
            return history, "", update_status()

    # Proceed with PR generation
    if state.files_to_translate and state.current_file_content.get("translated"):
        current_file = state.files_to_translate[0]
        translated_content = state.current_file_content["translated"]
        response += "\n\n🚀 **Generating GitHub PR...**"

        pr_response = generate_github_pr(
            target_language=state.target_language,
            filepath=current_file,
            translated_content=translated_content,
            github_config=state.github_config,
        )
        response += f"\n{pr_response}"
    else:
        response = "❌ No translated file available. Please complete the translation process first."

    history.append(["GitHub PR creation request", response])
    return history, "", update_status()


def restart_handler(history):
    """Resets the state and UI."""
    global state
    state = ChatState()
    welcome_msg = get_welcome_message()
    new_hist = [[None, welcome_msg]]
    return new_hist, "", update_status(), gr.Tabs(selected=0)
