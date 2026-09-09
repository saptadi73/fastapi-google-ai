"""immutable taxonomy version snapshots"""
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '9b07c8d6e5fa'
down_revision = '8a96b7c5d4ef'
branch_labels = None
depends_on = None
SCHEMA = 'platform'

def upgrade():
    op.create_table('taxonomy_version',
    sa.Column('taxonomy_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('base_version', sa.Integer(), nullable=True),
    sa.Column('revision_no', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('definition_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('approved_by', sa.Uuid(as_uuid=False), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], [f'{SCHEMA}.app_user.id'], ),
    sa.ForeignKeyConstraint(['created_by'], [f'{SCHEMA}.app_user.id'], ),
    sa.ForeignKeyConstraint(['taxonomy_id'], [f'{SCHEMA}.taxonomy.id'], ),
    sa.ForeignKeyConstraint(['tenant_id', 'approved_by'], [f'{SCHEMA}.app_user.tenant_id', f'{SCHEMA}.app_user.id'], name='fk_tenant_taxonomy_version_approved_by_7af62ed0'),
    sa.ForeignKeyConstraint(['tenant_id', 'created_by'], [f'{SCHEMA}.app_user.tenant_id', f'{SCHEMA}.app_user.id'], name='fk_tenant_taxonomy_version_created_by_a10800b6'),
    sa.ForeignKeyConstraint(['tenant_id', 'taxonomy_id'], [f'{SCHEMA}.taxonomy.tenant_id', f'{SCHEMA}.taxonomy.id'], name='fk_tenant_taxonomy_version_taxonomy_id_7f022491'),
    sa.ForeignKeyConstraint(['tenant_id'], [f'{SCHEMA}.tenant.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_taxonomy_version_tenant_id'),
    sa.UniqueConstraint('tenant_id', 'taxonomy_id', 'version', name='uq_taxonomy_version'),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_platform_taxonomy_version_tenant_id'), 'taxonomy_version', ['tenant_id'], unique=False, schema=SCHEMA)
    # Only the currently available approved state can be reconstructed. Never
    # fabricate older snapshots from the current term set.
    connection = op.get_bind()
    target = sa.table('taxonomy_version',
                      sa.column('id', sa.Uuid(as_uuid=False)), sa.column('tenant_id', sa.Uuid(as_uuid=False)),
                      sa.column('taxonomy_id', sa.Uuid(as_uuid=False)), sa.column('version', sa.Integer()),
                      sa.column('base_version', sa.Integer()), sa.column('revision_no', sa.Integer()),
                      sa.column('status', sa.String()), sa.column('definition_json', postgresql.JSONB()),
                      sa.column('created_by', sa.Uuid(as_uuid=False)), sa.column('approved_by', sa.Uuid(as_uuid=False)),
                      sa.column('created_at', sa.DateTime(timezone=True)), sa.column('approved_at', sa.DateTime(timezone=True)),
                      schema=SCHEMA)
    for taxonomy in connection.execute(sa.text(f"SELECT * FROM {SCHEMA}.taxonomy WHERE status='APPROVED'")).mappings():
        terms = connection.execute(sa.text(
            f"SELECT id::text, code, label, parent_id::text, aliases, is_active FROM {SCHEMA}.taxonomy_term "
            "WHERE taxonomy_id=:taxonomy AND tenant_id=:tenant ORDER BY id"),
            {"taxonomy": taxonomy['id'], "tenant": taxonomy['tenant_id']}).mappings().all()
        connection.execute(target.insert().values(
            id=str(uuid4()), tenant_id=str(taxonomy['tenant_id']), taxonomy_id=str(taxonomy['id']),
            version=taxonomy['version'], base_version=None, revision_no=1, status='APPROVED',
            definition_json={"terms": [dict(term) for term in terms]}, created_by=str(taxonomy['created_by']),
            approved_by=str(taxonomy['approved_by']) if taxonomy['approved_by'] else None,
            created_at=taxonomy['created_at'], approved_at=taxonomy['approved_at']))

def downgrade():
    op.drop_index(op.f('ix_platform_taxonomy_version_tenant_id'), table_name='taxonomy_version', schema=SCHEMA)
    op.drop_table('taxonomy_version', schema=SCHEMA)
