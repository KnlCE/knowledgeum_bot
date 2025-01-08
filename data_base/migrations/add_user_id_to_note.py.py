from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('note', sa.Column('user_id', sa.String(), nullable=False))
    op.add_column('note', sa.Column('catalog', sa.Integer(), sa.ForeignKey('catalog.id')))
    
def downgrade():
    op.drop_column('note', 'user_id')
    op.drop_column('note', 'catalog')
