"""
test_link_filter.py - URL and Link Removal Filter Unit Tests

This module tests the LinkFilter class which removes various types
of links from document content before embedding:
- HTML anchor tags (<a href="...">text</a>)
- Markdown links ([text](url))
- Plain URLs (http://, https://)
- Mixed content with multiple link types

Run with:
    python -m pytest test_link_filter.py -v
"""

import unittest
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.link_filter import LinkFilter

class TestLinkFilter(unittest.TestCase):
    def setUp(self):
        self.filter = LinkFilter()

    def test_html_link_removal(self):
        text = 'Check out <a href="http://example.com">Example</a> website.'
        expected = 'Check out Example website.'
        self.assertEqual(self.filter.filter_content(text), expected)

        text_nested = 'Link <a href="http://test.com"><b>Bold</b></a>.'
        expected = 'Link <b>Bold</b>.'
        self.assertEqual(self.filter.filter_content(text_nested), expected)

    def test_markdown_link_removal(self):
        text = 'This is a [link](http://example.com) to click.'
        expected = 'This is a link to click.'
        self.assertEqual(self.filter.filter_content(text), expected)

    def test_plain_url_removal(self):
        text = 'Visit http://example.com for more info.'
        expected = 'Visit  for more info.'
        self.assertEqual(self.filter.filter_content(text), expected)
        
        text_https = 'Secure site: https://secure.com/path?query=1'
        expected = 'Secure site: '
        self.assertEqual(self.filter.filter_content(text_https), expected)

    def test_mixed_content(self):
        text = 'Click [here](http://md.com) or <a href="http://html.com">here</a> or visit https://plain.com.'
        expected = 'Click here or here or visit .'
        self.assertEqual(self.filter.filter_content(text), expected)

    def test_metadata_preservation(self):
        metadata = {
            "url": "http://keep.me",
            "source": "http://original.source",
            "info": {"link": "https://nested.com"}
        }
        # Should return exactly the same
        result = self.filter.filter_metadata(metadata)
        self.assertEqual(result, metadata)
        self.assertEqual(result['url'], "http://keep.me")

    def test_no_url_traces(self):
        # User requirement: "Ensure filtered body does not contain ANY URL traces"
        text = 'Link [Google](http://google.com) and <a href="https://yahoo.com">Yahoo</a>'
        result = self.filter.filter_content(text)
        self.assertNotIn('http', result)
        self.assertNotIn('//', result)
        self.assertNotIn('.com', result) # Depending on context, .com might remain if it was part of text, but here checking URL parts

if __name__ == '__main__':
    unittest.main()
