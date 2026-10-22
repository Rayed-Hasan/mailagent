"""Label mapper for converting classifications to consistent labels."""

from typing import List

from mailagent.core.types import EmailCategory


class LabelMapper:
    """Maps email classifications to consistent display labels."""

    # Classification to label mapping
    CATEGORY_TO_LABELS = {
        EmailCategory.MEETS_REPLY: ["Needs Reply", "Inbox"],
        EmailCategory.FYI: ["Read Later", "Inbox"],
        EmailCategory.NEWSLETTER: ["Newsletter"],
        EmailCategory.PROMO: ["Promotion"],
        EmailCategory.RECEIVED: ["Receipt", "Finance"],
        EmailCategory.NOTIFICATION: ["Notification"],
        EmailCategory.SPAM: ["Spam"],
        EmailCategory.PERSONAL: ["Personal", "Inbox"],
        EmailCategory.URGENT: ["Important", "Urgent"],
        EmailCategory.SENSITIVE: ["Important", "Security"],
    }

    # Priority-based additional labels
    HIGH_PRIORITY_THRESHOLD = 70
    HIGH_PRIORITY_LABELS = ["Important"]

    @classmethod
    def category_to_labels(cls, category: EmailCategory, priority_score: int = 0) -> List[str]:
        """Convert a category to a list of labels.

        Args:
            category: The email category
            priority_score: Priority score (0-100) for additional labeling

        Returns:
            List of label names to apply
        """
        labels = cls.CATEGORY_TO_LABELS.get(category, ["Inbox"]).copy()

        # Add high priority label if applicable
        if priority_score >= cls.HIGH_PRIORITY_THRESHOLD:
            if "Important" not in labels:
                labels.append("Important")

        return labels

    @classmethod
    def is_system_label(cls, label: str) -> bool:
        """Check if a label is system-generated vs user-created."""
        system_labels = {
            "Needs Reply",
            "Read Later",
            "Newsletter",
            "Promotion",
            "Receipt",
            "Finance",
            "Notification",
            "Spam",
            "Personal",
            "Inbox",
            "Important",
            "Urgent",
            "Security",
        }
        return label in system_labels
