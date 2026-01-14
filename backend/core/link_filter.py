import re
from typing import Dict, Any, Optional

class LinkFilter:
    """
    Module for filtering links from text content while preserving them in metadata.
    """
    def __init__(self, config: Optional[Dict[str, bool]] = None):
        self.config = config or {
            "remove_html_links": True,
            "remove_markdown_links": True,
            "remove_plain_urls": True
        }
        
        # Regex for HTML links: <a href="...">text</a> -> matches full tag, captures text
        self.html_link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="[^"]*"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        
        # Regex for Markdown links: [text](url)
        # We use negative lookbehind (?<!!) to avoid matching images ![text](url) if desired, 
        # but to ensure "no URL traces", we might want to clean those too. 
        # However, the requirement specifically says [text](url). 
        # If we leave images, the URL inside might be caught by the plain URL filter later, breaking the image.
        # For text extraction purposes, usually we want the alt text or nothing.
        # Given the strict "no URL traces" rule, I will match standard markdown links.
        # If an image exists ![text](url), the plain URL filter will likely strip the URL part later.
        self.markdown_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        
        # Regex for Plain URLs
        # Use a more robust pattern that doesn't consume trailing punctuation like . , ; ? !
        # This matches http/https/www, followed by non-whitespace/non-brackets.
        # Then we strip trailing punctuation from the match if needed, but regex can be tricky.
        # Simpler approach: Match non-whitespace, but ensure it ends with alphanumeric or /
        self.url_pattern = re.compile(r'(https?://|www\.)[^\s()<>]+(?<![.,;?!])')

    def filter_content(self, text: str) -> str:
        """
        Filters links from the body text according to configuration.
        """
        if not text:
            return ""
            
        filtered_text = text
        
        # 1. Remove HTML links first
        if self.config.get("remove_html_links"):
            filtered_text = self.html_link_pattern.sub(r'\1', filtered_text)
            
        # 2. Remove Markdown links
        if self.config.get("remove_markdown_links"):
            filtered_text = self.markdown_link_pattern.sub(r'\1', filtered_text)
            
        # 3. Remove remaining plain URLs
        if self.config.get("remove_plain_urls"):
            filtered_text = self.url_pattern.sub('', filtered_text)
            
        return filtered_text

    def filter_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pass-through for metadata to ensure links are preserved.
        Returns the metadata object (or a copy if modification protection is strictly needed, 
        but here we just ensure we don't touch it).
        """
        # Requirement: Preserve all metadata links.
        return metadata
