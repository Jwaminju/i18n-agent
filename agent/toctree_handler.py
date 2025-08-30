import yaml
import requests
from typing import Dict, List, Any
import os

class TocTreeHandler:
    def __init__(self, project: str = "transformers"):
        from translator.project_config import get_project_config
        self.project = project
        self.project_config = get_project_config(project)
        
        # Extract repository path from config
        repo_path = self.project_config.repo_url.replace("https://github.com/", "")
        
        # Build project-specific URLs
        self.en_toctree_url = f"https://raw.githubusercontent.com/{repo_path}/main/docs/source/en/_toctree.yml"
        self.ko_toctree_url = f"https://raw.githubusercontent.com/{repo_path}/main/docs/source/ko/_toctree.yml"
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
   
    def find_and_update_translation_entry(self, ko_toctree_data, target_local: str, english_title: str, korean_title: str):
        """Find entry with '(번역중) 영어제목' and update it"""
        target_title_pattern = f"(번역중) {english_title}"
        
        def process_item(item):
            if isinstance(item, dict):
                # Check if title matches the pattern
                if item.get('title') == target_title_pattern:
                    # Update local path and title
                    item['local'] = target_local
                    item['title'] = korean_title
                    return True
                
                # Process sections recursively
                if 'sections' in item:
                    for section in item['sections']:
                        if process_item(section):
                            return True
            return False
        
        # Process the toctree data
        if isinstance(ko_toctree_data, list):
            for item in ko_toctree_data:
                if process_item(item):
                    return True
        return False

    def create_updated_toctree_with_replacement(self, ko_toctree: list, target_local: str) -> list:
        """Update Korean toctree by finding and updating translation entry"""
        try:
            # Step 1: Get English toctree and find the English title for target_local
            en_toctree = self.get_en_toctree()
            english_title = self.find_title_for_local(en_toctree, target_local)
            
            if not english_title:
                print(f"Could not find English title for local: {target_local}")
                return ko_toctree
            
            print(f"Found English title: {english_title} for local: {target_local}")
            
            # Step 2: Translate the English title to Korean
            korean_title = self.translate_title(english_title)
            print(f"Translated Korean title: {korean_title}")
            
            # Step 3: Make a deep copy to avoid modifying original
            import copy
            updated_toctree = copy.deepcopy(ko_toctree)
            
            # Step 4: Find and update the "(번역중) 영어제목" entry
            updated = self.find_and_update_translation_entry(
                updated_toctree, target_local, english_title, korean_title
            )
            
            if updated:
                print(f"Successfully updated translation entry: local={target_local}, title={korean_title}")
                return updated_toctree
            else:
                print(f"Could not find '(번역중) {english_title}' entry to update")
                return ko_toctree
                
        except Exception as e:
            print(f"Error creating updated toctree: {e}")
            return ko_toctree

    def find_title_for_local(self, toctree_data, target_local: str):
        """Find title for given local path in toctree"""
        def search_item(item):
            if isinstance(item, dict):
                if item.get('local') == target_local:
                    return item.get('title', '')
                
                if 'sections' in item:
                    for section in item['sections']:
                        result = search_item(section)
                        if result:
                            return result
            return None
        
        if isinstance(toctree_data, list):
            for item in toctree_data:
                result = search_item(item)
                if result:
                    return result
        return None

    def process_pr_commit(self, filepath: str):
        """Process PR commit by updating Korean toctree with translated entry"""
        # Get filepath without prefix
        filepath_without_prefix = filepath.replace("docs/source/en/", "").replace(".md", "")
        
        # Get Korean toctree
        ko_toctree = self.get_ko_toctree()
        
        # Update Korean toctree with replacement logic
        updated_ko_toctree = self.create_updated_toctree_with_replacement(ko_toctree, filepath_without_prefix)
        
        if not updated_ko_toctree:
            print(f"Failed to create updated Korean toctree for local: {filepath_without_prefix}")
            return
        
        print(f"Successfully updated Korean toctree")
        
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
        github_config: dict,
        project: str = "transformers"
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
