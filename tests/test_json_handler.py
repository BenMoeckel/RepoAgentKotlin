import unittest
from unittest.mock import mock_open, patch

from repo_agent.chat_with_repo.json_handler import (
    JsonFileProcessor,  # Adjust the import according to your project structure
)


class TestJsonFileProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = JsonFileProcessor("test.json")

    @patch("builtins.open", new_callable=mock_open, read_data='{"files": [{"objects": [{"md_content": "content1"}]}]}')
    def test_read_json_file(self, mock_file):
        # Test read_json_file method
        data = self.processor.read_json_file()
        self.assertEqual(data, {"files": [{"objects": [{"md_content": "content1"}]}]})
        mock_file.assert_called_with("test.json", "r", encoding="utf-8")

    @patch.object(JsonFileProcessor, 'read_json_file')
    def test_extract_md_contents(self, mock_read_json):
        # Test extract_md_contents method
        mock_read_json.return_value = {"App.kt": [{"name": "app", "code_content": "fun app() = 1", "md_content": ["content1"]}]}
        md_contents, extracted = self.processor.extract_data()
        self.assertIn("content1", md_contents)
        self.assertEqual(extracted[0]["code_content"], "fun app() = 1")

    @patch("builtins.open", new_callable=mock_open, read_data='{"App.kt": [{"name": "file1", "code_content": "fun file1() = 1", "md_content": ["docs"]}]}')
    def test_search_in_json_nested(self, mock_file):
        # Test search_in_json_nested method
        result = self.processor.search_code_contents_by_name("test.json", "file1")
        self.assertEqual(result, (["fun file1() = 1"], [["docs"]]))
        mock_file.assert_called_with("test.json", "r", encoding="utf-8")

    # Additional tests for error handling (FileNotFoundError, JSONDecodeError, etc.) can be added here

if __name__ == '__main__':
    unittest.main()
