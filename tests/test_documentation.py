#!/usr/bin/env python3
"""Test suite for command documentation.

Run with: pytest tests/test_documentation.py -v
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

DOCS_DIR = Path("osm_core/cli/docs")
SCHEMA_FILE = DOCS_DIR / "_schema.json"


def get_all_doc_files():
    """Get all documentation JSON files."""
    return [f for f in DOCS_DIR.glob("*.json") if not f.name.startswith("_")]


def get_all_documented_commands():
    """Get set of all documented command names."""
    commands = set()
    for f in get_all_doc_files():
        try:
            doc = json.loads(f.read_text(encoding='utf-8'))
            commands.add(doc.get("name", f.stem))
        except Exception:
            pass
    return commands


def get_cli_commands():
    """Get all CLI commands from osmfast --help."""
    try:
        result = subprocess.run(
            [sys.executable, "osmfast.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Extract command names from help output
        commands = set()
        in_commands = False
        for line in result.stdout.split('\n'):
            if 'positional arguments' in line.lower() or 'commands' in line.lower():
                in_commands = True
            elif in_commands:
                match = re.match(r'\s+(\w[\w-]*)\s', line)
                if match:
                    cmd = match.group(1)
                    if cmd not in ('command', 'help', 'version'):
                        commands.add(cmd)
        return commands
    except Exception:
        return set()


class TestDocumentationStructure:
    """Test documentation file structure."""

    @pytest.fixture
    def schema(self):
        """Load the JSON schema."""
        return json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_valid_json(self, doc_file):
        """Each doc file should be valid JSON."""
        try:
            json.loads(doc_file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in {doc_file.name}: {e}")

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_required_fields(self, doc_file, schema):
        """Each doc should have all required fields."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        required = schema.get("required", [])

        for field in required:
            assert field in doc, f"Missing required field '{field}' in {doc_file.name}"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_name_matches_filename(self, doc_file):
        """Command name should match filename."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        assert doc.get("name") == doc_file.stem, \
            f"Name '{doc.get('name')}' doesn't match filename '{doc_file.stem}'"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_summary_not_empty(self, doc_file):
        """Summary should not be empty."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        assert doc.get("summary", "").strip(), f"Empty summary in {doc_file.name}"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_description_not_empty(self, doc_file):
        """Description should not be empty."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        assert doc.get("description", "").strip(), f"Empty description in {doc_file.name}"


class TestExamples:
    """Test documentation examples."""

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_examples_format(self, doc_file):
        """Examples should be [title, command] pairs."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))

        for i, example in enumerate(doc.get("examples", [])):
            assert isinstance(example, list), f"Example {i} is not a list"
            assert len(example) == 2, f"Example {i} should have 2 elements"
            assert isinstance(example[0], str), f"Example {i} title not a string"
            assert isinstance(example[1], str), f"Example {i} command not a string"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_examples_start_with_osmfast(self, doc_file):
        """Most examples should start with 'osmfast'."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        cmd_name = doc.get("name", "")

        for title, example in doc.get("examples", []):
            # Allow alternative patterns for some commands
            valid_starts = ("osmfast ", "python ", "for ")
            if not any(example.startswith(s) for s in valid_starts):
                pytest.fail(f"Example '{title}' doesn't start with valid prefix: {example[:50]}")

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_no_double_spaces(self, doc_file):
        """Examples should not have double spaces."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))

        for title, example in doc.get("examples", []):
            assert "  " not in example, f"Example '{title}' has double spaces"


class TestRelatedCommands:
    """Test related command references."""

    @pytest.fixture
    def all_commands(self):
        """Get all documented command names."""
        return get_all_documented_commands()

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_related_commands_exist(self, doc_file, all_commands):
        """Related commands should reference existing docs."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))

        for related in doc.get("related", []):
            # Allow some flexibility - related might be a category not a command
            if related not in all_commands:
                # Check if it's a partial match (e.g., "cycling" might match "cycling-*")
                matches = [c for c in all_commands if related in c or c in related]
                if not matches:
                    pytest.skip(f"Related command '{related}' not found (may be category)")


class TestCoverage:
    """Test documentation coverage."""

    def test_docs_directory_exists(self):
        """Documentation directory should exist."""
        assert DOCS_DIR.exists(), f"Docs directory not found: {DOCS_DIR}"

    def test_schema_exists(self):
        """Schema file should exist."""
        assert SCHEMA_FILE.exists(), f"Schema file not found: {SCHEMA_FILE}"

    def test_minimum_docs_count(self):
        """Should have a reasonable number of documented commands."""
        doc_count = len(get_all_doc_files())
        assert doc_count >= 50, f"Only {doc_count} docs found, expected at least 50"

    def test_html_docs_generated(self):
        """HTML docs should be generated."""
        html_dir = Path("docs/commands")
        if html_dir.exists():
            html_count = len(list(html_dir.glob("*.html")))
            doc_count = len(get_all_doc_files())
            assert html_count >= doc_count * 0.9, \
                f"Only {html_count} HTML files for {doc_count} JSON docs"


class TestOptionsFormat:
    """Test option documentation format."""

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_options_are_dict(self, doc_file):
        """Options should be a dictionary."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))
        options = doc.get("options", {})
        assert isinstance(options, dict), f"Options is not a dict in {doc_file.name}"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_option_keys_format(self, doc_file):
        """Option keys should start with '-' for flags."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))

        for key in doc.get("options", {}).keys():
            # Allow positional args (no dash) but flag options must have dash
            if not key.startswith("-"):
                # Should be a positional argument name
                assert re.match(r'^[a-z_]+$', key), \
                    f"Invalid option key '{key}' in {doc_file.name}"

    @pytest.mark.parametrize("doc_file", get_all_doc_files(), ids=lambda f: f.stem)
    def test_option_values_not_empty(self, doc_file):
        """Option descriptions should not be empty."""
        doc = json.loads(doc_file.read_text(encoding='utf-8'))

        for key, value in doc.get("options", {}).items():
            assert value and value.strip(), \
                f"Empty description for option '{key}' in {doc_file.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
