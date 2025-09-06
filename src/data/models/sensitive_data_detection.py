"""
Sensitive Data Detection model for storing scan results.

This module defines the SensitiveDataDetection model that stores
detailed information about sensitive data found in documents.
"""

from typing import Optional
import uuid
from enum import Enum

from sqlalchemy import ForeignKey, Index, String, Text, Float, Integer, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Forward reference for Document model to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .document import Document


class SensitiveDataType(str, Enum):
    """Types of sensitive data that can be detected."""
    PERSONAL_ID = "personal_id"  # CCCD, CMND, Passport
    PHONE_NUMBER = "phone_number"  # Số điện thoại
    EMAIL = "email"  # Địa chỉ email
    ADDRESS = "address"  # Địa chỉ nhà
    BANK_ACCOUNT = "bank_account"  # Số tài khoản ngân hàng
    CREDIT_CARD = "credit_card"  # Số thẻ tín dụng
    TAX_ID = "tax_id"  # Mã số thuế
    SOCIAL_SECURITY = "social_security"  # Số BHXH
    MEDICAL_INFO = "medical_info"  # Thông tin y tế
    FINANCIAL_INFO = "financial_info"  # Thông tin tài chính
    GOVERNMENT_ID = "government_id"  # Số giấy tờ chính phủ
    CUSTOM = "custom"  # Loại tùy chỉnh khác


class ConfidenceLevel(str, Enum):
    """Confidence levels for detection accuracy."""
    LOW = "low"  # 0.3 - 0.5
    MEDIUM = "medium"  # 0.5 - 0.8
    HIGH = "high"  # 0.8 - 1.0


class SensitiveDataDetection(Base):
    """
    Model for storing sensitive data detection results.

    Each record represents a specific instance of sensitive data
    found in a document during scanning.
    """

    # Document relationship
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the document this detection belongs to"
    )

    # Detection details
    data_type: Mapped[SensitiveDataType] = mapped_column(
        SQLEnum(SensitiveDataType),
        nullable=False,
        index=True,
        doc="Type of sensitive data detected"
    )

    detected_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The actual sensitive text that was detected"
    )

    masked_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Masked version of the detected text for display"
    )

    # Location information
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Page number where the data was found (for PDFs)"
    )

    chunk_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Chunk index where the data was found"
    )

    context: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Surrounding context where the sensitive data was found"
    )

    # Detection confidence and metadata
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Confidence score from 0.0 to 1.0"
    )

    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        SQLEnum(ConfidenceLevel),
        nullable=False,
        doc="Categorized confidence level"
    )

    # Pattern information
    detection_pattern: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Pattern or rule that triggered the detection"
    )

    # AI model information
    ai_model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="AI model used for this detection"
    )

    # Additional metadata
    detection_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional detection metadata"
    )

    # Review status
    reviewed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether this detection has been reviewed by an admin"
    )

    false_positive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether this detection was marked as false positive"
    )

    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Notes from manual review"
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="sensitive_data_detections",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """
        String representation of the detection.

        Returns:
            String representation showing data type and confidence
        """
        return f"<SensitiveDataDetection(type='{self.data_type}', confidence={self.confidence_score})>"

    @property
    def display_text(self) -> str:
        """
        Get display-safe version of detected text.

        Returns:
            Masked text for safe display
        """
        return self.masked_text

    @property
    def is_high_confidence(self) -> bool:
        """
        Check if detection has high confidence.

        Returns:
            True if confidence level is HIGH
        """
        return self.confidence_level == ConfidenceLevel.HIGH

    @property
    def needs_review(self) -> bool:
        """
        Check if detection needs manual review.

        Returns:
            True if not reviewed and not marked as false positive
        """
        return not self.reviewed and not self.false_positive

    def mark_as_reviewed(self, notes: Optional[str] = None) -> None:
        """
        Mark detection as reviewed.

        Args:
            notes: Optional review notes
        """
        self.reviewed = True
        if notes:
            self.review_notes = notes

    def mark_as_false_positive(self, notes: Optional[str] = None) -> None:
        """
        Mark detection as false positive.

        Args:
            notes: Optional notes explaining why it's false positive
        """
        self.false_positive = True
        self.reviewed = True
        if notes:
            self.review_notes = notes

    @classmethod
    def get_confidence_level(cls, score: float) -> ConfidenceLevel:
        """
        Convert numeric confidence score to confidence level.

        Args:
            score: Confidence score from 0.0 to 1.0

        Returns:
            Corresponding confidence level
        """
        if score >= 0.8:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def mask_sensitive_data(self, text: str, data_type: SensitiveDataType) -> str:
        """
        Create a masked version of sensitive text.

        Args:
            text: Original sensitive text
            data_type: Type of sensitive data

        Returns:
            Masked version of the text
        """
        if data_type in [SensitiveDataType.PERSONAL_ID, SensitiveDataType.BANK_ACCOUNT]:
            # Show first 2 and last 2 characters
            if len(text) > 4:
                return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"
            else:
                return "*" * len(text)
        elif data_type == SensitiveDataType.EMAIL:
            # Mask username part
            if "@" in text:
                username, domain = text.split("@", 1)
                masked_username = f"{username[:2]}{'*' * (len(username) - 2)}"
                return f"{masked_username}@{domain}"
            return "*" * len(text)
        elif data_type == SensitiveDataType.PHONE_NUMBER:
            # Show first 3 and last 2 digits
            digits_only = ''.join(filter(str.isdigit, text))
            if len(digits_only) > 5:
                masked = f"{digits_only[:3]}{'*' * (len(digits_only) - 5)}{digits_only[-2:]}"
                return text.replace(digits_only, masked)
            return "*" * len(text)
        else:
            # Default masking: show first and last character
            if len(text) > 2:
                return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"
            else:
                return "*" * len(text)


# Create database indexes
Index('idx_sensitive_data_document_id', SensitiveDataDetection.document_id)
Index('idx_sensitive_data_type', SensitiveDataDetection.data_type)
Index('idx_sensitive_data_confidence_level',
      SensitiveDataDetection.confidence_level)
Index('idx_sensitive_data_reviewed', SensitiveDataDetection.reviewed)
Index('idx_sensitive_data_false_positive',
      SensitiveDataDetection.false_positive)
Index('idx_sensitive_data_created_at', SensitiveDataDetection.created_at)
