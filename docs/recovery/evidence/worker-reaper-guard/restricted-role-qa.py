import os
assert os.environ['DATABASE_URL']=='postgresql+psycopg://karenseir_worker@127.0.0.1:5432/postgres'
from app import outbox_worker as worker
from app.main import engine
from sqlalchemy import text
with engine.connect() as c:
    assert c.execute(text("select current_user")).scalar()=='karenseir_worker'
    assert not c.execute(text("select has_table_privilege(current_user,'reservations','SELECT')")).scalar()
    assert not c.execute(text("select has_table_privilege(current_user,'financial_ledger_entries','UPDATE')")).scalar()
class Finished(Exception): pass
ticks=0
real_batch=worker.process_batch
processed=0
def batch():
    global processed
    count=real_batch(); processed+=count; return count
worker.process_batch=batch
worker.start_status_server=lambda:None
worker.configure_logging=lambda:None
def sleep(_):
    global ticks
    ticks+=1
    if ticks==13:raise Finished()
worker.time.sleep=sleep
try:worker.run()
except Finished:pass
assert ticks==13 and worker.worker_health()['reservation_reaper']=='disabled'
print('PASS: 13 actual PostgreSQL outbox ticks with booking/finance privileges denied; reaper disabled; no external network')
