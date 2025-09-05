"""
GitHub PR Search Agent
An agent that finds a suitable reference PR when a reference PR URL is not provided.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Langchain imports
try:
    from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer
    from github import Github

    REQUIRED_LIBS_AVAILABLE = True
except ImportError as e:
    print(f"Required libraries are not installed: {e}")
    REQUIRED_LIBS_AVAILABLE = False

# Constants
DEFAULT_HF_MODEL_ID = "Helsinki-NLP/opus-mt-en-ko"
DEFAULT_TEMPERATURE = 0.0
# Fallback PR URL to ensure a PR is always returned
DEFAULT_FALLBACK_PR_URL = "https://github.com/huggingface/transformers/pull/24968"


class GitHubPRSearcher:
    """GitHub PR Searcher - now using a LangChain agent."""

    def _search_github_prs(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches GitHub for pull requests matching the query and returns the top 5 results.
        The query should be a valid GitHub search query.
        """
        logger.info(f"Executing GitHub search with query: {query}")
        try:
            issues = self.github_client.search_issues(query=query)
            # Take top 5 to keep context small for the agent
            top_issues = issues.get_page(0)[:5]

            if not top_issues:
                return []

            return [
                {"title": issue.title, "url": issue.html_url, "number": issue.number}
                for issue in top_issues
            ]
        except Exception as e:
            logger.error(f"Error during GitHub search: {e}", exc_info=True)
            # Return an error message that the agent can understand
            return [{"error": f"An error occurred during search: {e}"}]

    def __init__(self):
        if not REQUIRED_LIBS_AVAILABLE:
            raise ImportError("Required libraries for agent could not be found.")

        self._github_client = None
        self.llm_pipeline = None # Initialize Hugging Face pipeline here if needed later

    @property
    def github_client(self) -> Optional[Github]:
        """Lazy initialization of the GitHub API client."""
        if not REQUIRED_LIBS_AVAILABLE:
            raise ImportError("Required libraries could not be found.")

        if self._github_client is None:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                print("Warning: GITHUB_TOKEN environment variable is not set.")
                self._github_client = Github()  # Limited access
            else:
                self._github_client = Github(token)
        return self._github_client

    def find_best_reference_pr(
        self, owner: str, repo_name: str, target_language: str, context: str
    ):
        """
        Finds the best reference PR using a keyword-based search.
        Yields progress and returns the final PR URL.
        """
        message = "🤖 Searching for the best reference PR using keywords..."
        logger.info(message)
        yield message

        try:
            # Construct a robust search query
            query = f"repo:{owner}/{repo_name} is:pr is:merged \"{target_language}\" \"{context}\" i18n translation docs"
            
            # Execute GitHub search
            search_results = self._search_github_prs(query)

            if not search_results:
                message = "⚠️ No suitable PRs found. Using default PR."
                logger.warning(message)
                yield message
                return DEFAULT_FALLBACK_PR_URL

            # Simple logic to pick the best PR: just take the first one for now
            # In a more advanced scenario, an LLM could analyze titles/bodies
            best_pr_url = search_results[0]["url"]

            message = f"✅ Selected the best PR:\n`{best_pr_url}`"
            logger.info(f"Selected the best PR: {best_pr_url}")
            yield message
            return best_pr_url

        except Exception as e:
            message = f"❌ Error during PR search: {e}\nUsing default PR."
            logger.error(message, exc_info=True)
            yield message
            return DEFAULT_FALLBACK_PR_URL


def find_reference_pr_simple_stream(target_language: str = "", context: str = ""):
    """
    A simple function to find a reference PR, streaming progress.
    This function always searches in the 'huggingface/transformers' repository.
    """
    searcher = GitHubPRSearcher()
    stream_generator = searcher.find_best_reference_pr(
        "huggingface", "transformers", target_language, context
    )
    # The handler will receive the final URL from the generator's return statement
    final_url = yield from stream_generator

    # Format the final result as expected by the handler
    return {
        "status": "success",
        "result": f"Recommended PR URL: {final_url}",
        "repository": "huggingface/transformers",
        "target_language": target_language,
    }


# Example usage
if __name__ == "__main__":
    # Example execution for streaming
    # In a real application, a generator consumer (like the one in handler.py)
    # would process the yielded values. This script simulates that.
    print("--- Running Streaming Search Simulation ---")

    def run_simulation():
        """Simulates the consumption of the streaming generator."""
        test_gen = find_reference_pr_simple_stream(
            target_language="korean", context="docs"
        )
        try:
            while True:
                # This will print progress messages
                print(next(test_gen))
        except StopIteration as e:
            # When the generator is exhausted, the final result is in e.value
            print("\n--- FINAL RESULT ---")
            print(e.value)

    run_simulation()
