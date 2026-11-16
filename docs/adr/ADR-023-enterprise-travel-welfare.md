# ADR-023 — Enterprise travel and welfare

User requirements: docs/product/ENTERPRISE_TRAVEL_WELFARE_REQUIREMENTS.md.
Baseline aeac353, source/runtime main/operations content verified. Source and isolated
QA authorized. Production migration requires specific approval under AGENTS.md.

Use existing Organization, EmployeeAssignment, Department, CostCenter, Supplier,
Reservation, credit/ledger and outbox. New pre-booking EnterpriseRequest is not a
fake Reservation. Nine enterprise use cases share typed requirements but group/RFQ
requests are distinct from instant individual checkout. No financial method is
activated by a policy form or quote selection.

Add organization-scoped policy, explicit capability grants, request, immutable audit,
RFQ invitation and versioned supplier quote tables. Every table gets FORCE RLS and
explicit tenant predicates. Membership is necessary; generic tenant membership or a
finance role does not expose all employee requests. Requesters see only their own;
travel desk access and booking-on-behalf capability require an explicit grant.
Organization admins must themselves belong to the organization. Approvers are frozen
in the request policy snapshot, sequential, assigned members, and cannot self-approve.

A policy result is IN_POLICY / OUT_OF_POLICY / APPROVAL_REQUIRED / NOT_ALLOWED.
Store evaluated reasons and policy version. Unknown/no configured policy fails closed.
Budget in a request is an estimate, never reserved/spent credit. Supplier quotes are
real user-entered, versioned amounts; invited suppliers see redacted requirements,
not employee identity or the organization's internal budget. Selection validates
expiry and policy again. It is not a purchase/contract/charge or fulfillment claim.

Acceptance: isolated API/DB tests for owner/org/tenant boundaries, policy outcomes,
approval order/replay/self-approval, invited supplier quotes/revisions and selection;
real desktop/mobile UI→API→DB request and desk workflow; additive migration and RLS
checks against isolated PostgreSQL. No real SMS/payment or production fixtures.

Rollback: no existing table alteration. Keep old app images and the new tables on
application rollback. Destructive downgrade only for isolated QA; production must
not drop request/audit records. Prepare backup and exact migration/deploy commands
before asking for production approval.

## Master gap matrix extension
| Domain | Existing | This increment / remaining |
|---|---|---|
| Nine enterprise use cases | no pre-booking request aggregate | typed request + group RFQ |
| Hierarchy | organization/department/cost center/assignment | reuse; subsidiary/branch/project hierarchy remains |
| RBAC | coarse tenant roles | scoped configurable enterprise capabilities |
| Policy | booking/credit policy fragments | typed request policy + frozen outcomes; full fare/grade rules remain |
| Approvals | reservation-linked workflow | pre-booking sequential approvals with audit |
| Travel Desk | role overview | real open request/approval/RFQ queue |
| RFQ | absent | invitations, versioned quotes, selection; negotiation/contract/order/settlement remain |
| Budgets/benefits | credit ledger/cost-center budget | period/campaign allocations and family eligibility remain |
| Finance | existing checkout/credit/invoices | retain authorization; new methods not activated |
| Dashboard/reports | existing transaction views | no decorative metrics; enterprise scoped reporting remains |
| Enterprise assistant | consumer orchestration | structured group request handoff remains |
| Shared booking | common Reservation/Trip | request-to-reservation binding and delegated booking remain |

## Finance / gift requirements delta
Sources: ENTERPRISE_FINANCE_REQUIREMENTS.md and GIFT_BENEFIT_REQUIREMENTS.md.
The repeated gift attachment is one requirement, not two engines. Existing Wallet,
CreditAccount, FinancialLedgerEntry, InstallmentAgreement and ReconciliationRecord
are integration anchors. A campaign DRAFT records intent only: its proposed total
is not allocated, issued, funded or available credit. Bulk recipients are resolved
and validated server-side against organization membership. No delivery/token or
liability activation endpoint exists until funding and approved policy are wired.

| Added domain | Current implementation boundary | Internal work still required |
|---|---|---|
| Gift / benefit / campaign | persisted scoped campaign draft, bulk recipient validation, server total | funding linkage, approved issuance, claim/redeem, expiry, reports, consumer gifting |
| Enterprise finance | existing ledger/credit/installments/reconciliation retained | facility terms, atomic split funding, immutable balanced movements, source-aware refund integration |
| Settlement | existing settlement records retained | receivables/payables, statements, aging, reconciliation cases |
| Gift security/delivery | no redeemable token created for drafts | hashed single-purpose token, claim authorization, revocation, approved delivery |

All unfinished internal items remain development gaps, not external blockers.
Jabama supplied URL could not be retrieved by the browsing tool; no comparative
capability claim is based on that failed retrieval.
