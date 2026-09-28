import uuid
from test_checkout_reviews_zarinpal import login,auth


def test_prebooking_inquiry_is_owned_idempotent_and_does_not_relax_booking_support(client):
    employee=login(client,'employee@aftab.test');other=login(client,'supplier@aftab.test')
    key=str(uuid.uuid4());h={**auth(employee),'Idempotency-Key':key}
    payload={'subject':'QA venue inquiry','body':'Mock isolated request, no reservation','case_type':'SERVICE_INQUIRY'}
    first=client.post('/support/cases',headers=h,json=payload)
    assert first.status_code==201,first.text
    case=first.json();assert case['reservation_id'] is None and case['trip_id'] is None
    assert case['status']=='open' and len(case['messages'])==1
    assert client.post('/support/cases',headers=h,json=payload).json()['id']==case['id']
    assert client.post('/support/cases',headers=h,json={**payload,'body':'different content'}).status_code==409
    assert client.post('/support/cases',headers={**auth(other),'Idempotency-Key':key},json=payload).status_code==409
    assert case['id'] not in [r['id'] for r in client.get('/support/cases',headers=auth(other)).json()]
    mine=client.get('/support/cases',headers=auth(employee)).json()
    assert len([r for r in mine if r['id']==case['id']])==1
    assert client.post('/support/cases',headers={**h,'Idempotency-Key':str(uuid.uuid4())},json={**payload,'case_type':'OTHER'}).status_code==422
    assert client.post('/support/cases',headers={**h,'Idempotency-Key':str(uuid.uuid4())},json={**payload,'reservation_id':str(uuid.uuid4())}).status_code==404
