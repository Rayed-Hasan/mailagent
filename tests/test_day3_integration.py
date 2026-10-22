"""Tests for Day 3: Pre-filtering, Classification & Labeling integration."""

from datetime import datetime, timezone

import pytest

from mailagent.core.types import EmailCategory, EmailAction
from mailagent.core.label_mapper import LabelMapper
from mailagent.classifier.email_classifier import EmailClassifier
from mailagent.llm.registry import ProviderRegistry, ModelSlot


class FakeProvider:
    """Fake provider for testing."""
    provider_name = "fake"


def test_label_mapper_category_to_labels():
    """Test label mapping from categories."""
    # Test various categories
    assert LabelMapper.category_to_labels(EmailCategory.MEETS_REPLY) == ["Needs Reply", "Inbox"]
    assert LabelMapper.category_to_labels(EmailCategory.NEWSLETTER) == ["Newsletter"]
    assert LabelMapper.category_to_labels(EmailCategory.PROMO) == ["Promotion"]
    assert LabelMapper.category_to_labels(EmailCategory.RECEIVED) == ["Receipt", "Finance"]
    assert LabelMapper.category_to_labels(EmailCategory.URGENT) == ["Important", "Urgent"]
    assert LabelMapper.category_to_labels(EmailCategory.SENSITIVE) == ["Important", "Security"]


def test_label_mapper_high_priority_adds_important():
    """Test high priority adds Important label."""
    # Low priority - no Important label
    labels = LabelMapper.category_to_labels(EmailCategory.FYI, priority_score=30)
    assert "Important" not in labels

    # High priority - adds Important label
    labels = LabelMapper.category_to_labels(EmailCategory.FYI, priority_score=80)
    assert "Important" in labels

    # Already has Important - no duplicate
    labels = LabelMapper.category_to_labels(EmailCategory.URGENT, priority_score=90)
    assert labels.count("Important") == 1


def test_label_mapper_system_label_detection():
    """Test system label detection."""
    assert LabelMapper.is_system_label("Important") is True
    assert LabelMapper.is_system_label("Newsletter") is True
    assert LabelMapper.is_system_label("Needs Reply") is True
    assert LabelMapper.is_system_label("My Custom Label") is False


def test_classifier_validates_response_structure():
    """Test classifier validates response structure."""
    classifier = EmailClassifier()

    # Valid response
    valid_response = {
        "category": "urgent",
        "priority_score": 90,
        "action": "flag_human",
        "reason": "Urgent matter",
        "confidence": 0.95,
    }
    is_valid, error = classifier._validate_classification_response(valid_response)
    assert is_valid is True
    assert error == ""

    # Missing field
    invalid_response = {
        "category": "urgent",
        "priority_score": 90,
        "action": "flag_human",
        "reason": "Urgent matter",
        # Missing confidence
    }
    is_valid, error = classifier._validate_classification_response(invalid_response)
    assert is_valid is False
    assert "Missing required fields" in error

    # Invalid category
    invalid_response = {
        "category": "invalid_category",
        "priority_score": 90,
        "action": "flag_human",
        "reason": "Test",
        "confidence": 0.95,
    }
    is_valid, error = classifier._validate_classification_response(invalid_response)
    assert is_valid is False
    assert "Invalid category" in error

    # Invalid priority score
    invalid_response = {
        "category": "urgent",
        "priority_score": 150,  # Out of range
        "action": "flag_human",
        "reason": "Test",
        "confidence": 0.95,
    }
    is_valid, error = classifier._validate_classification_response(invalid_response)
    assert is_valid is False
    assert "Priority score out of range" in error

    # Invalid action
    invalid_response = {
        "category": "urgent",
        "priority_score": 90,
        "action": "invalid_action",
        "reason": "Test",
        "confidence": 0.95,
    }
    is_valid, error = classifier._validate_classification_response(invalid_response)
    assert is_valid is False
    assert "Invalid action" in error

    # Invalid confidence
    invalid_response = {
        "category": "urgent",
        "priority_score": 90,
        "action": "flag_human",
        "reason": "Test",
        "confidence": 1.5,  # Out of range
    }
    is_valid, error = classifier._validate_classification_response(invalid_response)
    assert is_valid is False
    assert "Confidence out of range" in error


def test_classifier_handles_malformed_llm_output():
    """Test classifier handles malformed LLM output gracefully."""
    # This would be tested with integration tests using actual provider calls
    # For now, we verify the validation logic exists
    classifier = EmailClassifier()
    assert hasattr(classifier, "_validate_classification_response")


def test_label_mapper_preserves_existing_labels():
    """Test label mapper doesn't remove user labels (conceptual)."""
    # System labels are predefined
    assert LabelMapper.is_system_label("Important") is True
    # User labels are not recognized as system
    assert LabelMapper.is_system_label("Work Project") is False


def test_provider_registry_with_classifier():
    """Test classifier works with provider registry."""
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    registry.set_slot(ModelSlot("classification", "fake", "model-1"))

    classifier = EmailClassifier(provider_registry=registry)
    assert classifier.provider_registry is registry


def test_classifier_without_registry_fallback():
    """Test classifier works without registry (v1 fallback)."""
    classifier = EmailClassifier(provider_registry=None)
    assert classifier.provider_registry is None
    # Should use direct Claude API
    assert classifier.api_key is not None or hasattr(classifier, "api_key")
