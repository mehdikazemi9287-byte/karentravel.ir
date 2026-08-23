"""Make financial_ledger_entries.wallet_id nullable and add credit_account_id,
so Organization Credit gets its own real ledger reservations/captures/releases
via the same append-only ledger primitive Wallet already uses, without merging
the two concepts (a ledger entry always references exactly one of the two).

Revision ID: 20260823_19
Revises: 20260823_18
"""
import sqlalchemy as sa
from alembic import op

revision = "20260823_19"
down_revision = "20260823_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("financial_ledger_entries")}
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("financial_ledger_entries") as batch:
            if columns.get("wallet_id") is not None and not columns["wallet_id"]["nullable"]:
                batch.alter_column("wallet_id", existing_type=sa.String(length=36), nullable=True)
            if "credit_account_id" not in columns:
                batch.add_column(sa.Column("credit_account_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key("fk_ledger_credit_account_id", "credit_accounts", ["credit_account_id"], ["id"])
                batch.create_index("ix_financial_ledger_entries_credit_account_id", ["credit_account_id"])
    else:
        if columns.get("wallet_id") is not None and not columns["wallet_id"]["nullable"]:
            op.alter_column("financial_ledger_entries", "wallet_id", existing_type=sa.String(length=36), nullable=True)
        if "credit_account_id" not in columns:
            op.add_column("financial_ledger_entries", sa.Column("credit_account_id", sa.String(length=36), nullable=True))
            op.create_foreign_key("fk_ledger_credit_account_id", "financial_ledger_entries", "credit_accounts", ["credit_account_id"], ["id"])
            op.create_index("ix_financial_ledger_entries_credit_account_id", "financial_ledger_entries", ["credit_account_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("financial_ledger_entries")}
    if "credit_account_id" not in columns:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("financial_ledger_entries") as batch:
            batch.drop_index("ix_financial_ledger_entries_credit_account_id")
            batch.drop_constraint("fk_ledger_credit_account_id", type_="foreignkey")
            batch.drop_column("credit_account_id")
            batch.alter_column("wallet_id", existing_type=sa.String(length=36), nullable=False)
    else:
        fk_name = None
        for fk in inspector.get_foreign_keys("financial_ledger_entries"):
            if fk.get("constrained_columns") == ["credit_account_id"]:
                fk_name = fk.get("name")
                break
        op.drop_index("ix_financial_ledger_entries_credit_account_id", table_name="financial_ledger_entries")
        if fk_name:
            op.drop_constraint(fk_name, "financial_ledger_entries", type_="foreignkey")
        op.drop_column("financial_ledger_entries", "credit_account_id")
        op.alter_column("financial_ledger_entries", "wallet_id", existing_type=sa.String(length=36), nullable=False)
