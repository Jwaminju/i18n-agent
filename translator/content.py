import re
import string

import requests
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer

from translator.prompt_glossary import PROMPT_WITH_GLOSSARY
from translator.project_config import get_project_config


def get_content(filepath: str, project: str = "transformers") -> str:
    if filepath == "":
        raise ValueError("No files selected for translation.")

    config = get_project_config(project)
    # Extract repo path from repo_url (e.g., "huggingface/transformers")
    repo_path = config.repo_url.replace("https://github.com/", "")
    
    url = f"https://raw.githubusercontent.com/{repo_path}/main/{filepath}"
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
    # to_translate = re.sub(r"```.*?```", "", to_translate, flags=re.DOTALL)
    ## remove markdown tables from text
    # to_translate = re.sub(r"^\|.*\|$\n?", "", to_translate, flags=re.MULTILINE)
    ## remove empty lines from text
    to_translate = re.sub(r"\n\n+", "\n\n", to_translate)
    return to_translate


def get_full_prompt(language: str, to_translate: str, additional_instruction: str = "") -> str:
    base_prompt = string.Template(
        "What do these sentences about Hugging Face Transformers "
        "(a machine learning library) mean in $language? "
        "Please do not translate the word after a 🤗 emoji "
        "as it is a product name. Output the complete markdown file**, with prose translated and all other content intact"
        "No explanations or extras—only the translated markdown. Also translate all comments within code blocks as well."
    ).safe_substitute(language=language)
    
    base_prompt += "\n\n```md"
    
    full_prompt = "\n".join([base_prompt, to_translate.strip(), "```", PROMPT_WITH_GLOSSARY])
    
    if additional_instruction.strip():
        full_prompt += f"\n\n🗒️ Additional instructions: {additional_instruction.strip()}"
    
    return full_prompt


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
    print("inner scaffold:")
    print(scaffold)
    return string.Template(scaffold)


def is_in_code_block(text: str, position: int) -> bool:
    """Check if a position in text is inside a code block"""
    text_before = text[:position]
    code_block_starts = text_before.count("```")
    return code_block_starts % 2 == 1


def fill_scaffold(content: str, to_translate: str, translated: str) -> str:
    scaffold = make_scaffold(content, to_translate)
    print("scaffold:")
    print(scaffold.template)
    
    # Get original text sections to maintain structure
    original_sections = to_translate.split("\n\n")
    
    # Split markdown sections to get headers and anchors
    divided = split_markdown_sections(to_translate)
    print("divided:")
    print(divided)
    anchors = get_anchors(divided)
    
    # Split translated content by markdown sections
    translated_divided = split_markdown_sections(translated)
    print("translated divided:")
    print(translated_divided)
    
    # Ensure we have the same number of headers as the original
    if len(translated_divided[1::3]) != len(anchors):
        print(f"Warning: Header count mismatch. Original: {len(anchors)}, Translated: {len(translated_divided[1::3])}")
        # Adjust anchors list to match translated headers
        if len(translated_divided[1::3]) < len(anchors):
            anchors = anchors[:len(translated_divided[1::3])]
        else:
            # Add empty anchors for extra headers
            anchors.extend([""] * (len(translated_divided[1::3]) - len(anchors)))
    
    # Add anchors to translated headers only if they're not in code blocks
    for i, korean_title in enumerate(translated_divided[1::3]):
        if i < len(anchors):
            # Find the position of this header in the original translated text
            header_pos = translated.find(korean_title.strip())
            if header_pos != -1 and not is_in_code_block(translated, header_pos):
                translated_divided[1 + i * 3] = f"{korean_title} {anchors[i]}"
            else:
                translated_divided[1 + i * 3] = korean_title
    
    # Reconstruct translated content with proper structure
    reconstructed_translated = "".join([
        "".join(translated_divided[i * 3 : i * 3 + 3]) 
        for i in range(len(translated_divided) // 3)
    ])
    
    # Split by double newlines to match original structure
    translated_sections = reconstructed_translated.split("\n\n")
    
    print("scaffold template count:")
    print(scaffold.template.count("$hf_i18n_placeholder"))
    print("original sections length:")
    print(len(original_sections))
    print("translated sections length:")
    print(len(translated_sections))
    
    # Ensure section counts match
    placeholder_count = scaffold.template.count("$hf_i18n_placeholder")
    
    if len(translated_sections) < placeholder_count:
        # Add empty sections if translated has fewer sections
        translated_sections.extend([""] * (placeholder_count - len(translated_sections)))
    elif len(translated_sections) > placeholder_count:
        # Truncate if translated has more sections
        translated_sections = translated_sections[:placeholder_count]
    
    # Final check
    if len(translated_sections) != placeholder_count:
        return f"Error: Section count mismatch. Expected: {placeholder_count}, Got: {len(translated_sections)}"
    
    translated_doc = scaffold.safe_substitute(
        {f"hf_i18n_placeholder{i}": text for i, text in enumerate(translated_sections)}
    )
    return translated_doc


def llm_translate(to_translate: str, huggingface_model_name: str) -> tuple[str, str]:
    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(huggingface_model_name)
        tokenizer = AutoTokenizer.from_pretrained(huggingface_model_name)
        translator = pipeline("translation", model=model, tokenizer=tokenizer)
        
        # The prompt already contains the source text, so we just pass it to the translator
        result = translator(to_translate, max_length=512)
        translated_content = result[0]['translation_text']
        
        # Placeholder for callback result, as transformers pipeline doesn't provide token usage directly
        status_message = f"✅ Translation completed using Hugging Face model: {huggingface_model_name}"
        return status_message, translated_content
    except Exception as e:
        return f"❌ Hugging Face Translation failed: {str(e)}", ""
