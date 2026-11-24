"""
Создаёт первого superadmin в базе данных.

Запуск (из папки backend/):
  python seed.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.user import User

SUPERADMIN_EMAIL = "admin@antiplagiat.uz"
SUPERADMIN_PASSWORD = "changeme123"


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == SUPERADMIN_EMAIL))
        if result.scalar_one_or_none():
            print(f"Superadmin already exists: {SUPERADMIN_EMAIL}")
            return

        user = User(
            email=SUPERADMIN_EMAIL,
            hashed_password=hash_password(SUPERADMIN_PASSWORD),
            full_name="Super Admin",
            role="superadmin",
            org_id=None,
            status="active",
        )
        db.add(user)
        await db.commit()

    print("=" * 50)
    print("Superadmin created successfully!")
    print(f"  Email:    {SUPERADMIN_EMAIL}")
    print(f"  Password: {SUPERADMIN_PASSWORD}")
    print("  IMPORTANT: change the password after first login!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
