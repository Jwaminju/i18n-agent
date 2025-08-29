"""Module for gradio chat-based translation agent interface."""

import base64
import os

import gradio as gr
from dotenv import load_dotenv

from agent.handler import (
    approve_handler,
    get_welcome_message,
    process_file_search_handler,
    restart_handler,
    send_message,
    start_translate_handler,
    sync_language_displays,
    update_prompt_preview,
    update_status,
    update_github_config,
)
from translator.model import Languages
from translator.project_config import get_available_projects

load_dotenv()


css = """
.gradio-container {
    background: linear-gradient(135deg, #ffeda7 0%, #ffbebf 100%);
}
.chat-container {
    background: rgba(255, 255, 180, 0.25);
    border-radius: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 1.0em;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,180,0.25);
    width: 100%;
    height: 100%;
}
.control-panel {
    background: rgba(255, 255, 180, 0.25);
    border-radius: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 1.0em;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,180,0.25);
    width: 100%;
    overflow: visible !important;

}
.status-card {
    width: 100%
}
.action-button {
    background: linear-gradient(135deg, #ff8c8c 0%, #f9a889 100%) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    transition: all 0.3s ease-in-out !important;
}
.action-button:hover {
    background: linear-gradient(135deg, #f9a889 0%, #ff8c8c 100%) !important;
    box-shadow: 0 6px 16px rgba(0,0,0,0.2) !important;
    transform: translateY(-2px) !important;
}

.simple-tabs .tab-nav button {
    background: transparent !important;
    color: #4A5568 !important;
    box-shadow: none !important;
    transform: none !important;
    border: none !important;
    border-bottom: 2px solid #E2E8F0 !important;
    border-radius: 0 !important;
    font-weight: 600 !important;
}

.simple-tabs .tab-nav button.selected {
    color: #f97316 !important;
    border-bottom: 2px solid #f97316 !important;
}

.simple-tabs .tab-nav button:hover {
    background: #f3f4f6 !important;
    color: #f97316 !important;
    box-shadow: none !important;
    transform: none !important;
}
"""


# Create the main interface
with gr.Blocks(
    css=css, title=" 🌐 Hugging Face Transformers Docs i18n made easy"
) as demo:
    # Title
    with open("images/hfkr_logo.png", "rb") as img_file:
        base64_img = base64.b64encode(img_file.read()).decode()
    gr.Markdown(
        f'<img src="data:image/png;base64,{base64_img}" style="display: block; margin-left: auto; margin-right: auto; height: 15em;"/>'
    )
    gr.Markdown(
        '<h1 style="text-align: center;"> 🌐 Hugging Face Transformers Docs i18n made easy</h1>'
    )

    # Content
    with gr.Row():
        # Chat interface
        with gr.Column(scale=3, elem_classes=["chat-container"]):
            gr.Markdown("### 🌐 Hugging Face i18n Agent")

            chatbot = gr.Chatbot(
                value=[[None, get_welcome_message()]], scale=1, height=585,
                show_copy_button=True
            )

        # Controller interface
        with gr.Column(scale=2):
            # Quick Controller
            with gr.Column(elem_classes=["control-panel"]):
                gr.Markdown("### 🛠️ Quick Controls")
                status_display = gr.HTML(update_status())

                with gr.Tabs(elem_classes="simple-tabs") as control_tabs:
                    with gr.TabItem("1. Find Files", id=0):
                        with gr.Group():
                            project_dropdown = gr.Radio(
                                choices=get_available_projects(),
                                label="🎯 Select Project",
                                value="transformers",
                            )
                            lang_dropdown = gr.Radio(
                                choices=[language.value for language in Languages],
                                label="🌍 Translate To",
                                value="ko",
                            )
                            k_input = gr.Number(
                                label="📊 First k missing translated docs",
                                value=10,
                                minimum=1,
                            )
                            find_btn = gr.Button(
                                "🔍 Find Files to Translate",
                                elem_classes="action-button",
                            )

                    with gr.TabItem("2. Translate", id=1):
                        with gr.Group():
                            files_to_translate = gr.Radio(
                                choices=[],
                                label="📄 Select a file to translate",
                                interactive=True,
                                value=None,
                            )
                            file_to_translate_input = gr.Textbox(
                                label="🌍 Select in the dropdown or write the file path to translate",
                                value="",
                            )

                            translate_lang_display = gr.Dropdown(
                                choices=[language.value for language in Languages],
                                label="🌍 Translation Language",
                                value="ko",
                                interactive=False,
                            )
                            anthropic_key = gr.Textbox(
                                label="🔑 Anthropic API key for translation generation",
                                type="password",
                            )
                            additional_instruction = gr.Textbox(
                                label="📝 Additional instructions (Optional - e.g., custom glossary)",
                                placeholder="Example: Translate 'model' as '모델' consistently",
                                lines=2,
                            )
                            
                            with gr.Accordion("🔍 Preview Prompt", open=False):
                                prompt_preview = gr.Textbox(
                                    label="Current Translation Prompt",
                                    lines=8,
                                    interactive=False,
                                    placeholder="Select a file and language to see the prompt preview...",
                                    show_copy_button=True,
                                )
                            
                            start_translate_btn = gr.Button(
                                "🚀 Start Translation", elem_classes="action-button"
                            )

                    with gr.TabItem("3. Upload PR", id=2):
                        with gr.Group():
                            github_token = gr.Textbox(
                                label="🔑 GitHub Token",
                                type="password",
                                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
                            )
                            github_owner = gr.Textbox(
                                label="👤 GitHub Owner/Username",
                                placeholder="your-username",
                            )
                            github_repo = gr.Textbox(
                                label="📁 Repository Name",
                                placeholder="your-repository",
                            )
                            reference_pr_url = gr.Textbox(
                                label="🔗 Reference PR URL (Optional - Agent will find one if not provided)",
                                placeholder="reference PR URL",
                            )

                            save_config_btn = gr.Button(
                                "💾 Save GitHub Config", elem_classes="action-button"
                            )
                            approve_btn = gr.Button(
                                "✅ Generate GitHub PR", elem_classes="action-button"
                            )
                            restart_btn = gr.Button(
                                "🔄 Restart Translation", elem_classes="action-button"
                            )

            # Chat Controller
            with gr.Column(elem_classes=["control-panel"]):
                gr.Markdown("### 💬 Chat with agent (Only simple chat is available)")
                msg_input = gr.Textbox(
                    placeholder="Type your message here... (e.g. 'what', 'how', or 'help')",
                    container=False,
                    scale=4,
                )
                send_btn = gr.Button("Send", scale=1, elem_classes="action-button")

    # Event Handlers

    find_btn.click(
        fn=process_file_search_handler,
        inputs=[project_dropdown, lang_dropdown, k_input, chatbot],
        outputs=[chatbot, msg_input, status_display, control_tabs, files_to_translate],
    )

    # Sync language across tabs
    lang_dropdown.change(
        fn=sync_language_displays,
        inputs=[lang_dropdown],
        outputs=[translate_lang_display],
    )

    #
    files_to_translate.change(
        fn=lambda x: x,
        inputs=[files_to_translate],
        outputs=[file_to_translate_input],
    )

    # Button event handlers
    start_translate_btn.click(
        fn=start_translate_handler,
        inputs=[chatbot, anthropic_key, file_to_translate_input, additional_instruction],
        outputs=[chatbot, msg_input, status_display, control_tabs],
    )

    # GitHub Config Save
    save_config_btn.click(
        fn=update_github_config,
        inputs=[github_token, github_owner, github_repo, reference_pr_url],
        outputs=[msg_input],
    )

    approve_btn.click(
        fn=approve_handler,
        inputs=[chatbot, github_owner, github_repo, reference_pr_url],
        outputs=[chatbot, msg_input, status_display],
    )

    restart_btn.click(
        fn=restart_handler,
        inputs=[chatbot],
        outputs=[chatbot, msg_input, status_display, control_tabs],
    )

    send_btn.click(
        fn=send_message,
        inputs=[msg_input, chatbot],
        outputs=[chatbot, msg_input, status_display],
    )

    msg_input.submit(
        fn=send_message,
        inputs=[msg_input, chatbot],
        outputs=[chatbot, msg_input, status_display],
    )

    # Update prompt preview when inputs change
    for input_component in [translate_lang_display, file_to_translate_input, additional_instruction]:
        input_component.change(
            fn=update_prompt_preview,
            inputs=[translate_lang_display, file_to_translate_input, additional_instruction],
            outputs=[prompt_preview],
        )

root_path = os.environ.get("GRADIO_ROOT_PATH")
demo.launch(root_path=root_path)
