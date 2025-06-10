import re
import string

import requests
from langchain.callbacks import get_openai_callback
from langchain_anthropic import ChatAnthropic


def get_content(filepath: str) -> str:
    url = string.Template(
        "https://raw.githubusercontent.com/huggingface/" "transformers/main/$filepath"
    ).safe_substitute(filepath=filepath)
    response = requests.get(url)
    if response.status_code == 200:
        content = response.text
        return content
    else:
        raise ValueError("Failed to retrieve content from the URL.", url)


def preprocess_content(content: str) -> str:
    # Extract text to translate from document

    ## ignore top license comment
    to_translate = content[content.find("#") :]
    ## remove code blocks from text
    to_translate = re.sub(r"```.*?```", "", to_translate, flags=re.DOTALL)
    ## remove markdown tables from text
    to_translate = re.sub(r"^\|.*\|$\n?", "", to_translate, flags=re.MULTILINE)
    ## remove empty lines from text
    to_translate = re.sub(r"\n\n+", "\n\n", to_translate)

    return to_translate


def get_full_prompt(language: str, to_translate: str) -> str:
    prompt = string.Template(
        "What do these sentences about Hugging Face Transformers "
        "(a machine learning library) mean in $language? "
        "Please do not translate the word after a 🤗 emoji "
        "as it is a product name. Output only the translated markdown result "
        "without any explanations or introductions.\n\n```md"
    ).safe_substitute(language=language)
    return "\n".join([prompt, to_translate.strip(), "```"])


def split_markdown_sections(markdown: str) -> list:
    # Find all titles using regular expressions
    return re.split(r"^(#+\s+)(.*)$", markdown, flags=re.MULTILINE)[1:]
    # format is like [level, title, content, level, title, content, ...]


def get_anchors(divided: list) -> list:
    anchors = []
    # from https://github.com/huggingface/doc-builder/blob/01b262bae90d66e1150cdbf58c83c02733ed4366/src/doc_builder/build_doc.py#L300-L302
    for title in divided[1::3]:
        anchor = re.sub(r"[^a-z0-9\s]+", "", title.lower())
        anchor = re.sub(r"\s{2,}", " ", anchor.strip()).replace(" ", "-")
        anchors.append(f"[[{anchor}]]")
    return anchors


def make_scaffold(content: str, to_translate: str) -> string.Template:
    scaffold = content
    for i, text in enumerate(to_translate.split("\n\n")):
        scaffold = scaffold.replace(text, f"$hf_i18n_placeholder{i}", 1)
    return string.Template(scaffold)


def fill_scaffold(content: str, to_translate: str, translated: str) -> str:
    scaffold = make_scaffold(content, to_translate)
    divided = split_markdown_sections(to_translate)
    anchors = get_anchors(divided)

    translated = split_markdown_sections(translated)

    translated[1::3] = [
        f"{korean_title} {anchors[i]}"
        for i, korean_title in enumerate(translated[1::3])
    ]
    translated = "".join(
        ["".join(translated[i * 3 : i * 3 + 3]) for i in range(len(translated) // 3)]
    ).split("\n\n")
    if newlines := scaffold.template.count("$hf_i18n_placeholder") - len(translated):
        return str(
            [
                f"Please {'recover' if newlines > 0 else 'remove'} "
                f"{abs(newlines)} incorrectly inserted double newlines."
            ]
        )

    translated_doc = scaffold.safe_substitute(
        {f"hf_i18n_placeholder{i}": text for i, text in enumerate(translated)}
    )
    return translated_doc


def llm_translate(to_translate: str) -> tuple[str, str]:
    with get_openai_callback() as cb:
        model = ChatAnthropic(
            model="claude-sonnet-4-20250514", max_tokens=64000, streaming=True
        )
        ai_message = model.invoke(to_translate)
        print("cb:", cb)
    return cb, ai_message.content
