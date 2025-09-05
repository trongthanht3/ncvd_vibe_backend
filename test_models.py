#!/usr/bin/env python3
"""
Test script for database models and connectivity.

This script tests the database connection and model functionality.
"""

import asyncio
import uuid
from datetime import datetime

from src.data.database import get_db_session, init_database
from src.data.repositories.user import UserRepository
from src.data.repositories.item import ItemRepository


async def test_database_connectivity():
    """Test database connectivity."""
    print("🔄 Testing database connectivity...")

    try:
        await init_database()
        print("✅ Database connectivity test passed!")
        return True
    except Exception as e:
        print(f"❌ Database connectivity test failed: {e}")
        return False


async def test_user_repository():
    """Test user repository operations."""
    print("\n🔄 Testing User repository...")

    try:
        session = await get_db_session()
        user_repo = UserRepository(session)

        # Test user creation
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "keycloak_sub": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
            "is_active": True
        }

        user = await user_repo.create(user_data)
        print(f"✅ Created user: {user.username} (ID: {user.id})")

        # Test user retrieval
        retrieved_user = await user_repo.get_by_id(user.id)
        print(f"✅ Retrieved user: {retrieved_user.full_name}")

        # Test user search
        users = await user_repo.search_users("test")
        print(f"✅ Found {len(users)} users matching 'test'")

        # Test user update
        updated_user = await user_repo.update(user.id, {"bio": "Test user bio"})
        print(f"✅ Updated user bio: {updated_user.bio}")

        # Clean up
        await session.commit()
        await session.close()

        print("✅ User repository tests passed!")
        return True

    except Exception as e:
        print(f"❌ User repository test failed: {e}")
        if 'session' in locals():
            await session.rollback()
            await session.close()
        return False


async def test_item_repository():
    """Test item repository operations."""
    print("\n🔄 Testing Item repository...")

    try:
        session = await get_db_session()
        user_repo = UserRepository(session)
        item_repo = ItemRepository(session)

        # First create a user to own the item
        user_data = {
            "username": "itemowner",
            "email": "owner@example.com",
            "keycloak_sub": str(uuid.uuid4()),
            "is_active": True
        }
        user = await user_repo.create(user_data)

        # Test item creation
        item_data = {
            "title": "Test Item",
            "description": "This is a test item",
            "content": "Some test content",
            "owner_id": user.id,
            "is_public": True,
            "category": "test"
        }

        item = await item_repo.create(item_data)
        print(f"✅ Created item: {item.title} (ID: {item.id})")

        # Test item retrieval
        retrieved_item = await item_repo.get_by_id(item.id)
        print(f"✅ Retrieved item: {retrieved_item.display_title}")

        # Test items by owner
        owner_items = await item_repo.get_by_owner(user.id)
        print(f"✅ Found {len(owner_items)} items for owner")

        # Test public items
        public_items = await item_repo.get_public_items()
        print(f"✅ Found {len(public_items)} public items")

        # Test item update
        updated_item = await item_repo.update(item.id, {"view_count": 10})
        print(f"✅ Updated item view count: {updated_item.view_count}")

        # Test increment methods
        await item_repo.increment_view_count(item.id)
        await item_repo.increment_like_count(item.id)
        refreshed_item = await item_repo.get_by_id(item.id)
        print(
            f"✅ Incremented counts - Views: {refreshed_item.view_count}, Likes: {refreshed_item.like_count}")

        # Clean up
        await session.commit()
        await session.close()

        print("✅ Item repository tests passed!")
        return True

    except Exception as e:
        print(f"❌ Item repository test failed: {e}")
        if 'session' in locals():
            await session.rollback()
            await session.close()
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting database and model tests...\n")

    # Test database connectivity
    db_ok = await test_database_connectivity()
    if not db_ok:
        print("❌ Database tests failed. Exiting.")
        return

    # Test repositories
    user_ok = await test_user_repository()
    item_ok = await test_item_repository()

    print("\n🎯 Test Summary:")
    print(f"   Database Connectivity: {'✅' if db_ok else '❌'}")
    print(f"   User Repository: {'✅' if user_ok else '❌'}")
    print(f"   Item Repository: {'✅' if item_ok else '❌'}")

    if all([db_ok, user_ok, item_ok]):
        print("\n🎉 All tests passed! Data layer is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())
