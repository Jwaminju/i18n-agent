import yaml
import requests
from typing import Dict, List, Any
import os

class TocTreeHandler:
    def __init__(self):
        self.en_toctree_url = "https://raw.githubusercontent.com/huggingface/transformers/main/docs/source/en/_toctree.yml"
        self.ko_toctree_url = "https://raw.githubusercontent.com/huggingface/transformers/main/docs/source/ko/_toctree.yml"
        self.local_docs_path = "docs/source/ko"
    
    def fetch_toctree(self, url: str) -> Dict[str, Any]:
        """Fetch and parse YAML from URL"""
        response = requests.get(url)
        response.raise_for_status()
        return yaml.safe_load(response.text)
    
    def get_en_toctree(self) -> Dict[str, Any]:
        """Get English toctree structure"""
        return self.fetch_toctree(self.en_toctree_url)
    
    def get_ko_toctree(self) -> Dict[str, Any]:
        """Get Korean toctree structure"""
        return self.fetch_toctree(self.ko_toctree_url)
    
    def extract_title_mappings(self, en_data: List[Dict], ko_data: List[Dict]) -> Dict[str, str]:
        """Extract title mappings between English and Korean"""
        mappings = {}
        
        def process_section(en_section: Dict, ko_section: Dict):
            if 'local' in en_section and 'local' in ko_section:
                if en_section['local'] == ko_section['local']:
                    en_title = en_section.get('title', '')
                    ko_title = ko_section.get('title', '')
                    if en_title and ko_title:
                        mappings[en_title] = ko_title
            
            if 'sections' in en_section and 'sections' in ko_section:
                en_sections = en_section['sections']
                ko_sections = ko_section['sections']
                
                for i, en_sub in enumerate(en_sections):
                    if i < len(ko_sections):
                        process_section(en_sub, ko_sections[i])
        
        for i, en_item in enumerate(en_data):
            if i < len(ko_data):
                process_section(en_item, ko_data[i])
        
        return mappings
    
    def translate_title(self, en_title: str) -> str:
        """Translate English title to Korean using LLM"""
        try:
            from translator.content import llm_translate
            
            prompt = f"""Translate the following English documentation title to Korean. Return only the translated title, nothing else.

English title: {en_title}

Korean title:"""
            
            callback_result, translated_title = llm_translate(prompt)
            return translated_title.strip()
        except Exception as e:
            print(f"Error translating title '{en_title}': {e}")
            return en_title
    
    def create_local_toctree(self, en_title: str, local_file_path: str) -> Dict[str, str]:
        """Create local toctree entry with Korean title and local path"""
        try:
            # First try to get Korean title from existing mappings
            en_data = self.get_en_toctree()
            ko_data = self.get_ko_toctree()
            
            title_mappings = self.extract_title_mappings(en_data, ko_data)
            ko_title = title_mappings.get(en_title)
            
            # If no existing mapping, translate the title
            if not ko_title:
                ko_title = self.translate_title(en_title)
            
            return {
                'local': local_file_path,
                'title': ko_title
            }
        except Exception as e:
            print(f"Error creating local toctree: {e}")
            return {
                'local': local_file_path,
                'title': en_title
            }
   
    def create_updated_toctree_with_llm(self, en_toctree_yaml: str, ko_toctree_yaml: str, target_local: str) -> dict:
        """Use LLM to create updated Korean toctree with new entry at correct position"""
        try:
            from translator.content import llm_translate
            
            prompt = f"""You are given English and Korean toctree YAML structures. You need to:

1. Find the entry(local, title) with `- local: {target_local}` in the English toctree
2. Translate its title to Korean
3. Insert this new entry into the Korean toctree at the same position as it appears in the English toctree
4. Return the complete updated Korean toctree

English toctree YAML:
```yaml
{en_toctree_yaml}
```

Current Korean toctree YAML:
```yaml
{ko_toctree_yaml}
```

Target local path to add: "{target_local}"

Return the complete updated Korean toctree in YAML format:
```yaml
# Updated Korean toctree with new entry inserted at correct position
[complete toctree structure here]
```

Important positioning rules:
- Find the exact position (index and nesting level) of the target entry in the English toctree
- Count from the beginning: if it's the 5th item in English toctree, it should be the 5th item in Korean toctree
- If it's inside a 'sections' array, maintain that nesting structure
- Keep all existing Korean entries in their current positions
- Insert the new Korean entry at the exact same position as the English entry
- If there are gaps in positions (missing entries), maintain those gaps
- Preserve the exact YAML structure: {{local: "path", title: "title"}} or {{local: "path", title: "title", sections: [...]}}

Example: If English entry is at position [2] (3rd item), insert Korean entry at position [2] in Korean toctree
Example: If English entry is at position [1]['sections'][0] (1st item in sections of 2nd entry), insert at same nested position"""
            
            callback_result, response = llm_translate(prompt)
            
            # Parse YAML response
            response = response.strip()
            
            try:
                # Extract YAML content between ```yaml and ```
                if "```yaml" in response:
                    yaml_start = response.find("```yaml") + 7
                    yaml_end = response.find("```", yaml_start)
                    yaml_content = response[yaml_start:yaml_end].strip()
                else:
                    yaml_content = response
                
                updated_ko_toctree = yaml.safe_load(yaml_content)
                return updated_ko_toctree
            except Exception as e:
                print(f"Failed to parse LLM YAML response: {e}")
                print(f"Response was: {response}")
                return None
                
        except Exception as e:
            print(f"Error using LLM to create updated toctree: {e}")
            return None

    def process_pr_commit(self, filepath: str):
        """Process PR commit by using LLM to create complete updated Korean toctree"""
        # Get filepath without prefix
        filepath_without_prefix = filepath.replace("docs/source/en/", "").replace(".md", "")
        
        # Get English and Korean toctrees as YAML strings
        en_toctree = self.get_en_toctree()
        ko_toctree = self.get_ko_toctree()
        
        en_toctree_yaml = yaml.dump(en_toctree, allow_unicode=True, default_flow_style=False)
        ko_toctree_yaml = yaml.dump(ko_toctree, allow_unicode=True, default_flow_style=False)
        
        # Use LLM to create updated Korean toctree
        updated_ko_toctree = self.create_updated_toctree_with_llm(en_toctree_yaml, ko_toctree_yaml, filepath_without_prefix)
        
        if not updated_ko_toctree:
            print(f"Failed to create updated Korean toctree for local: {filepath_without_prefix}")
            return
        
        print(f"LLM successfully updated Korean toctree")
        
        # Store the updated toctree for commit
        self.updated_ko_toctree = updated_ko_toctree

    def commit_and_push_toctree(self, pr_agent, owner: str, repo_name: str, branch_name: str):
        """Commit and push toctree updates as a separate commit"""
        try:
            # Use the updated toctree created by LLM
            if not hasattr(self, 'updated_ko_toctree') or not self.updated_ko_toctree:
                print("No updated Korean toctree available")
                return {"status": "error", "message": "No updated toctree to commit"}
                
            ko_data = self.updated_ko_toctree
            
            # Convert to YAML string
            toctree_content = yaml.dump(ko_data, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            # Create toctree commit message
            commit_message = "docs: update Korean documentation table of contents"
            
            # Commit toctree file
            file_result = pr_agent.create_or_update_file(
                owner=owner,
                repo_name=repo_name,
                path="docs/source/ko/_toctree.yml",
                message=commit_message,
                content=toctree_content,
                branch_name=branch_name
            )
            
            if file_result.startswith("SUCCESS"):
                return {
                    "status": "success", 
                    "message": f"Toctree committed successfully: {file_result}",
                    "commit_message": commit_message
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Toctree commit failed: {file_result}"
                }
                
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Error committing toctree: {str(e)}"
            }

    def update_toctree_after_translation(
        self,
        translation_result: dict, 
        filepath: str, 
        pr_agent, 
        github_config: dict
    ) -> dict:
        """Update toctree after successful translation PR.
        
        Args:
            translation_result: Result from translation PR workflow
            filepath: Original file path
            pr_agent: GitHub PR agent instance
            github_config: GitHub configuration dictionary
            
        Returns:
            Dictionary with toctree update result
        """
        if translation_result["status"] == "error":
            return None
            
        try:
            # Process toctree update with LLM
            self.process_pr_commit(filepath)
            # Commit toctree as separate commit
            print("self.updated_ko_toctree:", self.updated_ko_toctree:)
            if self.updated_ko_toctree:
                return self.commit_and_push_toctree(
                    pr_agent=pr_agent,
                    owner=github_config["owner"],
                    repo_name=github_config["repo_name"],
                    branch_name=translation_result["branch"]
                )

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error updating toctree: {str(e)}"
            }
