"""AI Marketing generator — produces Amazon listings, social posts, and email campaigns.

Uses the existing AIService to generate structured marketing content for a book
based on its title, description, chapters, and target audience.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from models.accounts import User
from models.assets import MarketingAsset
from models.book_writing import WritingBook, WritingChapter
from models.enums import MarketingAssetType
from services.ai_service import AIService as AISvc

MARKETING_ASSET_CONFIGS = {
    MarketingAssetType.AMAZON_DESCRIPTION: {
        "label": "Amazon Description",
        "description": "Book description optimized for Amazon's product page.",
        "prompt_key": "amazon_description",
        "system_prompt": (
            "You are an Amazon KDP marketing expert. Write compelling product descriptions "
            "that convert browsers into buyers. Use benefit-driven language, include a hook, "
            "describe what the reader will gain, and end with a call to action."
        ),
    },
    MarketingAssetType.SUBTITLE: {
        "label": "Subtitle Ideas",
        "description": "Generated subtitle suggestions for your book.",
        "prompt_key": "subtitle",
        "system_prompt": (
            "You are a book marketing specialist. Generate 5 compelling subtitle options "
            "for a book. Each subtitle should be concise (under 15 words), clear about the "
            "book's value proposition, and contain relevant keywords."
        ),
    },
    MarketingAssetType.KEYWORDS: {
        "label": "Keywords",
        "description": "Amazon search keywords for discoverability.",
        "prompt_key": "keywords",
        "system_prompt": (
            "You are an Amazon KDP keyword specialist. Generate 7-10 high-volume, "
            "relevant search keywords/phrases for a book's Amazon listing. Include "
            "both short-tail and long-tail keywords."
        ),
    },
    MarketingAssetType.CATEGORIES: {
        "label": "Categories",
        "description": "Recommended Amazon book categories.",
        "prompt_key": "categories",
        "system_prompt": (
            "You are an Amazon KDP category expert. Suggest 2-3 primary and 2-3 secondary "
            "book categories for Amazon listing. Explain why each category is a good fit."
        ),
    },
    MarketingAssetType.PINTEREST_POST: {
        "label": "Pinterest Post",
        "description": "Engaging Pinterest pin description.",
        "prompt_key": "pinterest",
        "system_prompt": (
            "You are a social media marketer for books. Write an engaging Pinterest pin "
            "description with 2-5 relevant hashtags. Include a compelling hook and clear value."
        ),
    },
    MarketingAssetType.INSTAGRAM_CAPTION: {
        "label": "Instagram Caption",
        "description": "Book promotion caption for Instagram.",
        "prompt_key": "instagram",
        "system_prompt": (
            "You are a book-focused Instagram marketer. Write an engaging caption for a book "
            "promotion post. Include a hook, 1-2 emojis, a relatable insight, and relevant hashtags."
        ),
    },
    MarketingAssetType.FACEBOOK_POST: {
        "label": "Facebook Post",
        "description": "Book promotion post for Facebook.",
        "prompt_key": "facebook",
        "system_prompt": (
            "You are a Facebook book marketer. Write a conversational, click-worthy post "
            "promoting a book. Include a relatable hook and a call to action."
        ),
    },
    MarketingAssetType.X_POST: {
        "label": "X (Twitter) Post",
        "description": "Concise book promotion for X/Twitter.",
        "prompt_key": "x_post",
        "system_prompt": (
            "You write viral book marketing tweets. Write a punchy, shareable post under 280 "
            "characters that grabs attention and links to the book."
        ),
    },
    MarketingAssetType.LINKEDIN_POST: {
        "label": "LinkedIn Post",
        "description": "Professional book promotion for LinkedIn.",
        "prompt_key": "linkedin",
        "system_prompt": (
            "You write LinkedIn content for authors and thought leaders. Write a professional "
            "post about a book that positions the author as an expert. Include a key insight "
            "and a call to engage."
        ),
    },
    MarketingAssetType.EMAIL_PROMOTION: {
        "label": "Email Launch Campaign",
        "description": "3-email launch sequence for your mailing list.",
        "prompt_key": "email_promotion",
        "system_prompt": (
            "You are an email marketing specialist for book launches. Generate a 3-email launch "
            "campaign: (1) teaser/announcement, (2) value-focused with excerpts, (3) launch day "
            "call to action. Each email should have a subject line and body."
        ),
    },
}


class MarketingEngine:
    """Generates AI marketing assets for a book."""

    def __init__(self, ai_service: AISvc) -> None:
        self._ai = ai_service

    async def generate(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
        asset_type_str: str,
    ) -> MarketingAsset:
        """Generate a single marketing asset for a book."""
        asset_type = MarketingAssetType(asset_type_str.upper())
        config = MARKETING_ASSET_CONFIGS.get(asset_type)
        if config is None:
            raise ResourceNotFoundError(f"Marketing asset type '{asset_type_str}' not supported.")

        book = await session.get(WritingBook, book_id)
        if book is None or book.deleted_at is not None:
            raise ResourceNotFoundError("Book not found.")
        if book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")

        chapters_result = await session.execute(
            select(WritingChapter)
            .where(WritingChapter.book_id == book_id, WritingChapter.deleted_at.is_(None))
            .order_by(WritingChapter.chapter_number),
        )
        chapters = list(chapters_result.scalars())

        # Build context for the AI.
        chapter_summaries = "\n".join(
            f"- Ch {ch.chapter_number}: {ch.title} ({len((ch.content or '').split())} words)"
            for ch in chapters[:5]
        )
        content_snippet = ""
        if chapters and chapters[0].content:
            snippet = chapters[0].content[:500]
            content_snippet = f"\n\nFirst chapter excerpt:\n{snippet}"

        user_prompt = f"""Book Title: {book.title}
{('Subtitle: ' + book.subtitle) if book.subtitle else ''}
Author: {book.author_name or 'Unknown'}
Target Audience: {book.target_audience or 'General readers'}
Description: {book.description or 'Not provided'}
Language: {book.language or 'en'}

Chapter structure:
{chapter_summaries}{content_snippet}

Generate a high-quality {config['label'].lower()} for this book."""

        result = await self._ai.generate_text(
            system_prompt=config["system_prompt"],
            user_prompt=user_prompt,
        )

        # Delete previous asset of same type for this book.
        prev_result = await session.execute(
            select(MarketingAsset).where(
                MarketingAsset.book_id == book_id,
                MarketingAsset.asset_type == asset_type.value,
            ),
        )
        for prev in prev_result.scalars():
            await session.delete(prev)

        asset = MarketingAsset(
            book_id=book_id,
            asset_type=asset_type.value,
            content=result.text,
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        return asset

    async def list_assets(
        self,
        session: AsyncSession,
        user: User,
        book_id: UUID,
    ) -> list[MarketingAsset]:
        """List all generated marketing assets for a book."""
        book = await session.get(WritingBook, book_id)
        if book is None or book.user_id != user.id:
            raise ResourceNotFoundError("Book not found.")
        result = await session.execute(
            select(MarketingAsset).where(MarketingAsset.book_id == book_id),
        )
        return list(result.scalars())

    async def get_asset(
        self,
        session: AsyncSession,
        user: User,
        asset_id: UUID,
    ) -> MarketingAsset:
        """Get a single marketing asset with ownership check."""
        asset = await session.get(MarketingAsset, asset_id)
        if asset is None or asset.deleted_at is not None:
            raise ResourceNotFoundError("Marketing asset not found.")
        book = await session.get(WritingBook, asset.book_id)
        if book is None or book.user_id != user.id:
            raise ResourceNotFoundError("Marketing asset not found.")
        return asset

    async def delete_asset(
        self,
        session: AsyncSession,
        user: User,
        asset_id: UUID,
    ) -> None:
        """Delete a marketing asset."""
        asset = await self.get_asset(session, user, asset_id)
        await session.delete(asset)
        await session.commit()

    @staticmethod
    def available_types() -> list[dict[str, str]]:
        """Return metadata for all available marketing asset types."""
        return [
            {
                "type": asset_type.value,
                "label": config["label"],
                "description": config["description"],
            }
            for asset_type, config in MARKETING_ASSET_CONFIGS.items()
        ]


def get_marketing_engine(ai_service: AISvc) -> MarketingEngine:
    """Return a (non-singleton) marketing engine using the provided AI service."""
    return MarketingEngine(ai_service)