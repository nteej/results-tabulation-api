"""empty message

Revision ID: 315344af891e
Revises: 7e18dab4e23b
Create Date: 2019-10-27 21:58:30.375338

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '315344af891e'
down_revision = '7e18dab4e23b'
branch_labels = None
depends_on = None


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('submission', sa.Column('submittedVersionId', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'submission', 'submissionVersion', ['submittedVersionId'], ['submissionVersionId'])
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'submission', type_='foreignkey')
    op.drop_column('submission', 'submittedVersionId')
    ### end Alembic commands ###
