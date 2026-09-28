import uuid
from test_checkout_reviews_zarinpal import reservation_fixture,auth

def test_support_retry_matches_body_and_denies_customer_agent_action(client):
    user,r,_,_=reservation_fixture(client,uuid.uuid4().hex);key=uuid.uuid4().hex;headers={**auth(user),'Idempotency-Key':key};data={'reservation_id':r['id'],'subject':'Mock QA support','body':'Mock QA original','priority':'normal'}
    first=client.post('/support/cases',headers=headers,json=data);assert first.status_code==201
    assert client.post('/support/cases',headers=headers,json=data).json()['id']==first.json()['id']
    assert client.post('/support/cases',headers=headers,json={**data,'body':'Mock QA different'}).status_code==409
    assert client.post('/support/cases/'+first.json()['id']+'/human-replies',headers=auth(user),json={'body':'Mock QA forbidden'}).status_code==403
