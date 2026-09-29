"""Pre-booking enterprise domain; existing reservation and ledger remain authoritative."""
from typing import Optional
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Integer, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .operations import OperationalMixin

class EnterpriseGrant(OperationalMixin, Base):
    __tablename__='enterprise_grants'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    permissions_json: Mapped[str]=mapped_column(Text,default='[]')
    __table_args__=(UniqueConstraint('tenant_id','organization_id','user_id',name='uq_enterprise_grant'),)

class EnterprisePolicy(OperationalMixin, Base):
    __tablename__='enterprise_policies'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    version: Mapped[int]=mapped_column(Integer)
    rules_json: Mapped[str]=mapped_column(Text)
    __table_args__=(UniqueConstraint('tenant_id','organization_id','version',name='uq_enterprise_policy_version'),)

class EnterpriseRequest(OperationalMixin, Base):
    __tablename__='enterprise_requests'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    requester_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    use_case: Mapped[str]=mapped_column(String(40),index=True)
    title: Mapped[str]=mapped_column(String(200))
    status: Mapped[str]=mapped_column(String(32),index=True)
    requirements_json: Mapped[str]=mapped_column(Text)
    policy_snapshot_json: Mapped[str]=mapped_column(Text)
    policy_result: Mapped[str]=mapped_column(String(32))
    current_step: Mapped[int]=mapped_column(Integer,default=0)
    selected_quote_id: Mapped[Optional[str]]=mapped_column(String(36),nullable=True)

class EnterpriseRequestEvent(OperationalMixin, Base):
    __tablename__='enterprise_request_events'
    request_id: Mapped[Optional[str]]=mapped_column(ForeignKey('enterprise_requests.id'),nullable=True,index=True)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    actor_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    event_type: Mapped[str]=mapped_column(String(64))
    detail_json: Mapped[str]=mapped_column(Text)
    command_key: Mapped[str]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('tenant_id','command_key',name='uq_enterprise_event_command'),)

class EnterpriseInvitation(OperationalMixin, Base):
    __tablename__='enterprise_invitations'
    request_id: Mapped[str]=mapped_column(ForeignKey('enterprise_requests.id'),index=True)
    supplier_id: Mapped[str]=mapped_column(ForeignKey('suppliers.id'),index=True)
    __table_args__=(UniqueConstraint('tenant_id','request_id','supplier_id',name='uq_enterprise_invitation'),)

class EnterpriseQuote(OperationalMixin, Base):
    __tablename__='enterprise_quotes'
    request_id: Mapped[str]=mapped_column(ForeignKey('enterprise_requests.id'),index=True)
    supplier_id: Mapped[str]=mapped_column(ForeignKey('suppliers.id'),index=True)
    revision: Mapped[int]=mapped_column(Integer)
    amount: Mapped[int]=mapped_column(BigInteger)
    currency: Mapped[str]=mapped_column(String(3),default='IRR')
    terms: Mapped[str]=mapped_column(Text)
    valid_until: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('tenant_id','request_id','supplier_id','revision',name='uq_enterprise_quote_revision'),)

class BenefitCampaign(OperationalMixin, Base):
    __tablename__='benefit_campaigns'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    name: Mapped[str]=mapped_column(String(200))
    product_type: Mapped[str]=mapped_column(String(40))
    status: Mapped[str]=mapped_column(String(24),default='DRAFT')
    amount_per_recipient: Mapped[int]=mapped_column(BigInteger)
    proposed_total: Mapped[int]=mapped_column(BigInteger)
    currency: Mapped[str]=mapped_column(String(3),default='IRR')
    recipient_ids_json: Mapped[str]=mapped_column(Text)
    rules_json: Mapped[str]=mapped_column(Text)
    personalization_json: Mapped[str]=mapped_column(Text)
    valid_from: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime]=mapped_column(DateTime(timezone=True))

class EnterpriseBookingLink(OperationalMixin, Base):
    __tablename__='enterprise_booking_links'
    request_id: Mapped[str]=mapped_column(ForeignKey('enterprise_requests.id'),index=True)
    reservation_id: Mapped[str]=mapped_column(ForeignKey('reservations.id'),index=True)
    linked_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    __table_args__=(UniqueConstraint('tenant_id','reservation_id',name='uq_enterprise_link_reservation'),)
