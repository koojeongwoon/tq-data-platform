"""
Prompt templates for welfare policy chatbot

This module centralizes all LLM prompts used across the application.
"""

from shared.prompts.welfare import (
    # RAG Service prompts
    WELFARE_SYSTEM_PROMPT,
    build_rag_user_message,

    # Intent classification
    INTENT_CLASSIFICATION_SYSTEM,
    build_intent_classification_prompt,

    # Slot extraction
    SLOT_EXTRACTION_SYSTEM,
    build_slot_extraction_prompt,

    # General question handling
    GENERAL_QUESTION_SYSTEM,
    build_general_question_prompt,
)

__all__ = [
    # RAG Service
    "WELFARE_SYSTEM_PROMPT",
    "build_rag_user_message",

    # Intent classification
    "INTENT_CLASSIFICATION_SYSTEM",
    "build_intent_classification_prompt",

    # Slot extraction
    "SLOT_EXTRACTION_SYSTEM",
    "build_slot_extraction_prompt",

    # General question
    "GENERAL_QUESTION_SYSTEM",
    "build_general_question_prompt",
]
