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
    update_status,
    update_github_config,
)
from translator.model import Languages

load_dotenv()


css = """
.gradio-container {
    background: linear-gradient(135deg, #ffeda7 0%, #ffbebf 100%);
}
.chat-container {
    background: rgba(255, 255, 180, 0.25);
    border-radius: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 1.5em;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,180,0.25);
    width: 100%;
    height: 100%;
}
.control-panel {
    background: rgba(255, 255, 180, 0.25);
    border-radius: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 1.5em;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,180,0.25);
    width: 100%;
}
.status-card {
    width: 100%
}
"""


# Create the main interface
with gr.Blocks(css=css, title=" 🌐 Hugging Face Transformers Docs i18n made easy") as demo:

    # Title
    with open("images/hfkr_logo.png", "rb") as img_file:
        base64_img = base64.b64encode(img_file.read()).decode()
    gr.Markdown(
        f'<img src="data:image/png;base64,{base64_img}" style="display: block; margin-left: auto; margin-right: auto; height: 15em;"/>'
    )
    gr.Markdown('<h1 style="text-align: center;"> 🌐 Hugging Face Transformers Docs i18n made easy</h1>')

    # Content
    with gr.Row():
        # Chat interface
        with gr.Column(scale=4, elem_classes=["chat-container"]):
            gr.Markdown("### 🌐 Hugging Face i18n Agent")

            chatbot = gr.Chatbot(
                value=[[None, get_welcome_message()]], scale=1, height=585
            )

        # Controller interface
        with gr.Column(scale=2):
            # Quick Controller
            with gr.Column(elem_classes=["control-panel"]):
                gr.Markdown("### 🛠️ Quick Controls")
                status_display = gr.HTML(update_status())

                with gr.Tabs() as control_tabs:
                    with gr.TabItem("1. Find Files", id=0):
                        with gr.Group():
                            lang_dropdown = gr.Dropdown(
                                choices=[language.value for language in Languages],
                                label="🌍 Translate To",
                                value="ko",
                            )
                            k_input = gr.Number(
                                label="📊 First k missing translated docs",
                                value=1,
                                minimum=1,
                                maximum=100,
                            )
                            find_btn = gr.Button(
                                "🔍 Find Files to Translate",
                                variant="primary",
                                size="lg",
                            )

                    with gr.TabItem("2. Translate", id=1):
                        with gr.Group():
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
                            start_translate_btn = gr.Button(
                                "🚀 Start Translation", variant="primary"
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
                                "💾 Save GitHub Config", variant="secondary"
                            )
                            approve_btn = gr.Button(
                                "✅ Generate GitHub PR", variant="primary"
                            )
                            restart_btn = gr.Button(
                                "🔄 Restart Translation", variant="secondary"
                            )

            # Chat Controller
            with gr.Column(elem_classes=["control-panel"]):
                gr.Markdown("### 💬 Chat with agent")
                msg_input = gr.Textbox(
                    placeholder="Type your message here... (e.g. 'what', 'how', or 'help')",
                    container=False,
                    scale=4,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)

    # Event Handlers

    find_btn.click(
        fn=process_file_search_handler,
        inputs=[lang_dropdown, k_input, chatbot],
        outputs=[chatbot, msg_input, status_display, control_tabs],
    )

    # Sync language across tabs
    lang_dropdown.change(
        fn=sync_language_displays,
        inputs=[lang_dropdown],
        outputs=[translate_lang_display],
    )

    # Button event handlers
    start_translate_btn.click(
        fn=start_translate_handler,
        inputs=[chatbot, anthropic_key],
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

root_path = os.environ.get("GRADIO_ROOT_PATH")
demo.launch(root_path=root_path)
