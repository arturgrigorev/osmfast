"""Tests for XML utilities."""
import pytest
from osm_core.utils.xml_utils import xml_escape


class TestXmlEscape:
    """Tests for xml_escape function."""

    def test_ampersand(self):
        """Test ampersand escaping."""
        assert xml_escape("Tom & Jerry") == "Tom &amp; Jerry"

    def test_less_than(self):
        """Test less-than escaping."""
        assert xml_escape("a < b") == "a &lt; b"

    def test_greater_than(self):
        """Test greater-than escaping."""
        assert xml_escape("a > b") == "a &gt; b"

    def test_double_quote(self):
        """Test double quote escaping."""
        assert xml_escape('say "hello"') == "say &quot;hello&quot;"

    def test_single_quote(self):
        """Test single quote escaping."""
        assert xml_escape("it's") == "it&#39;s"

    def test_all_special(self):
        """Test all special characters."""
        input_str = '<tag k="name" v=\'Tom & Jerry\'>'
        expected = "&lt;tag k=&quot;name&quot; v=&#39;Tom &amp; Jerry&#39;&gt;"
        assert xml_escape(input_str) == expected

    def test_unicode_preserved(self):
        """Test unicode characters are preserved."""
        assert xml_escape("Café résumé") == "Café résumé"

    def test_empty_string(self):
        """Test empty string."""
        assert xml_escape("") == ""

    def test_numeric_input(self):
        """Test numeric input is converted."""
        assert xml_escape(123) == "123"
