"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("author", "public", name="userrole"), nullable=False, server_default="author"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    # Posts table
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(600), unique=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Enum("draft", "scheduled", "published", name="poststatus"), nullable=False, server_default="draft"),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("search_vector", TSVECTOR()),
    )
    op.create_index("ix_posts_id", "posts", ["id"])
    op.create_index("ix_posts_slug", "posts", ["slug"])
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_published_at", "posts", ["published_at"])
    op.create_index("ix_posts_search_vector", "posts", ["search_vector"], postgresql_using="gin")

    # Create trigger function for search_vector update
    op.execute("""
        CREATE OR REPLACE FUNCTION posts_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER posts_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, content ON posts
        FOR EACH ROW EXECUTE FUNCTION posts_search_vector_update();
    """)

    # Post revisions table
    op.create_table(
        "post_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title_snapshot", sa.String(500), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("revision_author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision_timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_post_revisions_id", "post_revisions", ["id"])
    op.create_index("ix_post_revisions_post_id", "post_revisions", ["post_id"])
    op.create_index("ix_post_revisions_revision_author_id", "post_revisions", ["revision_author_id"])

    # Media table
    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_media_id", "media", ["id"])
    op.create_index("ix_media_author_id", "media", ["author_id"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS posts_search_vector_trigger ON posts")
    op.execute("DROP FUNCTION IF EXISTS posts_search_vector_update()")
    op.drop_table("media")
    op.drop_table("post_revisions")
    op.drop_table("posts")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS poststatus")
