from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('note', sa.Column('user_id', sa.String(), nullable=False))
    op.add_column('note', sa.Column('marker', sa.Integer(), sa.ForeignKey('marker.id')))
    
def downgrade():
    op.drop_column('note', 'user_id')
    op.drop_column('note', 'marker')
