"""add task version and backfill companion values

Revision ID: 30ffbaee18cd
Revises: 647c510a77b1
Create Date: 2021-05-19 16:55:43.724884

"""
from typing import Iterator

from alembic import context, op
from sqlalchemy.orm import Session

from redun.backends import db
from redun.task import Task
from redun.utils import pickle_dumps
from redun.value import MIME_TYPE_PICKLE

# revision identifiers, used by Alembic.
revision = "30ffbaee18cd"
down_revision = "647c510a77b1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
    # Data migration

    # Do not try to do data migration in offline mode.
    if context.is_offline_mode():
        return

    session = Session(bind=op.get_bind())
    try:
        backfill_values_for_lonely_tasks(session)
    finally:
        session.close()


def downgrade():
    # Deliberate choice to not roll back `backfill_values_for_lonely_tasks`
    # ### commands auto generated by Alembic - please adjust! ###
    # ### end Alembic commands ###
    pass


# Data migration helpers
def backfill_values_for_lonely_tasks(session: Session) -> None:
    """
    Create a Value record corresponding to every Task in the database, if it doesn't already exist.
    """
    lonely_db_tasks = get_lonely_tasks(session)
    for db_task in lonely_db_tasks:
        # We can't get `func` from the registry, so we use a dummy function when instantiating
        # the `redun.Task` corresponding to the `db_task`. This is acceptable for our needs since
        # func is not consulted during serialization when other parameters (like version) are
        # passed as arguments.
        redun_task = Task(
            func=lambda: None,
            name=db_task.name,
            namespace=db_task.namespace,
            compat=[],  # Missing from db record
            script=guess_is_script(db_task),
            task_options={},  # Missing from task record & not hashed until very recently
        )
        session.add(
            db.Value(
                value_hash=db_task.hash,
                type=Task.type_name,
                format=MIME_TYPE_PICKLE,
                value=pickle_dumps(redun_task),
            )
        )
    if session.new:
        session.commit()


def get_lonely_tasks(session: Session) -> Iterator[db.Task]:
    """
    Query the database for all Tasks that don't have corresponding Value records
    """
    return session.query(db.Task).filter_by(value=None).all()


def guess_is_script(task: db.Task) -> bool:
    """
    Check whether an input task is among those known to be script tasks. This is a best-guess
    based on perusing existing redun usage in the insitro GitHub organization, so it's likely that
    there will be some false-negatives.
    """
    known_script_tasks = {
        "redun.script_task",
        "test_help",
        "test_help_debug",
        "test_gfetch",
    }
    return task.fullname in known_script_tasks
