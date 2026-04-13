"""Database layer — asyncpg pool + raw SQL queries.

Decision: No ORM. Direct SQL via asyncpg (binary protocol, built-in pool,
automatic JSONB ↔ dict conversion). See architecture Decision #1.
"""
