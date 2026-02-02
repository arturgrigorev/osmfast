"""Base filter classes and data structures."""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class FilterRule:
    """Represents a single filter rule.

    Defines criteria for accepting or rejecting OSM elements based on
    their type and tag values.
    """
    action: str  # 'accept' or 'reject'
    element_type: str  # 'nodes', 'ways', 'relations', or '*'
    key: Optional[str] = None
    value: Optional[str] = None  # '*' means any value
    values: Optional[List[str]] = None  # for multiple values

    def matches(self, element_type: str, tags: dict) -> bool:
        """Check if an element matches this filter rule.

        Args:
            element_type: 'nodes', 'ways', or 'relations'
            tags: Element's tag dictionary

        Returns:
            True if the element matches this rule
        """
        # Check element type
        if self.element_type != '*' and self.element_type != element_type:
            return False

        # If no key specified, matches all elements of the type
        if not self.key:
            return True

        # Check if key exists
        if self.key not in tags:
            return False

        # Check value(s)
        tag_value = tags[self.key]

        if self.values:
            # Multiple specific values
            return tag_value in self.values
        elif self.value == '*':
            # Any value acceptable
            return True
        elif self.value:
            # Specific value
            return tag_value == self.value

        return True

    def __str__(self) -> str:
        """String representation for debugging."""
        if self.values:
            value_str = ','.join(self.values)
        else:
            value_str = self.value or '*'

        return f"{self.action}:{self.element_type}:{self.key}={value_str}"
