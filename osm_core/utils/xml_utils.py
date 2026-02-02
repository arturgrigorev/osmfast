"""XML utility functions - single source of truth."""


def xml_escape(text: str) -> str:
    """Escape special XML characters.

    Args:
        text: Raw text to escape

    Returns:
        XML-safe escaped string

    Examples:
        >>> xml_escape("Tom & Jerry")
        'Tom &amp; Jerry'
        >>> xml_escape("<script>")
        '&lt;script&gt;'
    """
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))
