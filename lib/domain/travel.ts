export type TripStage = 'before' | 'during' | 'after';
export type BookingStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed';
export type VoucherStatus = 'pending' | 'issued' | 'void';
export type MerchantRelation = 'contracted' | 'credit-enabled' | 'external';
export type ServiceCategory = 'pre-trip' | 'transfer' | 'food' | 'experience' | 'souvenir' | 'wellness' | 'essential';
export type ServiceGroup = 'before-trip'|'mobility'|'stay'|'food'|'experience'|'travel-commerce';
export type BookableServiceType = 'flight'|'hotel'|'accommodation'|'train'|'tour'|'car-rental'|'transfer'|'experience'|'other';
export type AfterSalesCaseType = 'voluntary'|'provider-disruption'|'exceptional'|'platform-error';
export type AfterSalesRequestStatus = 'submitted'|'reviewing'|'waiting-provider'|'user-action-required'|'approved'|'rejected'|'refunding'|'refunded'|'closed';
export type PolicyAvailability = 'verified'|'verification-required'|'unavailable';
export type TripEventSeverity = 'info'|'important'|'critical';
export type TripEventSource = 'system'|'provider'|'ai'|'human_support';
export type TripEventStatus = 'pending-verification'|'verified'|'resolved';
export type NotificationChannel = 'in_app'|'push'|'sms';
export type NotificationPreferenceTopic = 'important-trip-changes'|'booking-updates'|'refund-change-updates'|'support-messages';

export interface Traveller { id:string; fullName:string; type:'adult'|'child'; documentHint:string }
export interface TripSegment { id:string; mode:'flight'|'train'|'road'; origin:string; destination:string; departure:string; arrival:string; carrierLabel:string }
export interface Booking { id:string; type:'transport'|'accommodation'|'service'; serviceType?:BookableServiceType; title:string; status:BookingStatus; supplierLabel:string; reference:string; disruptionStatus?:'none'|'reported'|'provider-change' }
export interface Voucher { id:string; bookingId:string; status:VoucherStatus; title:string; issuedAt?:string }
export interface ItineraryItem { id:string; stage:TripStage; dateLabel:string; title:string; detail:string; status:'done'|'upcoming'|'optional' }
export interface Trip { id:string; title:string; origin:string; destination:string; startDate:string; endDate:string; durationLabel:string; status:BookingStatus; stage:TripStage; travellers:Traveller[]; segments:TripSegment[]; bookings:Booking[]; vouchers:Voucher[]; itinerary:ItineraryItem[]; events?:TripEvent[]; accommodation?:{name:string; address:string; checkIn:string; checkOut:string; status:BookingStatus}; organizationContext?:{tenantLabel:string; eligibilityStatus:'unknown'|'eligible'|'ineligible'; authoritative:false} }
export interface Service { id:string; title:string; category:ServiceCategory; group:ServiceGroup; action:'مشاهده'|'انتخاب'|'رزرو'|'استفاده'|'دریافت خدمت'; description:string; destination?:string; availability:'mock'|'unavailable'|'live'; href?:string; creditCapability:'sample-enabled'|'not-applicable'|'unknown'; alreadyPurchased?:boolean }
export interface Merchant { id:string; name:string; category:ServiceCategory; relation:MerchantRelation; benefit?:Benefit }
export interface NearbyPlace { id:string; merchant?:Merchant; name:string; category:string; distanceLabel:string; openState:'unknown'|'open'|'closed'; sourceLabel:string; latitude:number; longitude:number }
export interface Wallet { id:string; ownerType:'personal'|'organization'; status:'unknown'|'active'|'inactive'; balance?:never }
export interface Credit { id:string; walletId:string; status:'unknown'|'eligible'|'ineligible'; amount?:never }
export interface Benefit { id:string; label:string; kind:'discount'|'credit'|'perk'; valueLabel?:string; mock:true }
export interface TripNotification { id:string; tripId:string; stage:TripStage; title:string; body:string; deepLink:string; kind:'booking'|'reminder'|'arrival'|'nearby'|'voucher'|'after-sales'|'disruption' }
export interface TripEvent { id:string; tripId:string; bookingId?:string; type:string; severity:TripEventSeverity; title:string; message:string; occurredAt:string; effectiveAt?:string; source:TripEventSource; requiresAction:boolean; status:TripEventStatus; deepLink?:string }
export interface NotificationPreference { topic:NotificationPreferenceTopic; channels:Record<NotificationChannel,boolean> }
export interface NotificationDispatch { eventId:string; tripId:string; channel:NotificationChannel; deepLink:string; status:'not-sent'; reason:'mock-provider'|'channel-disabled' }

export interface CancellationPolicy { availability:PolicyAvailability; refundable:'yes'|'no'|'unknown'; freeCancellationDeadline?:string; penaltyBasis?:string; noShowRule?:string; providerVerificationRequired:boolean }
export interface RefundPolicy { availability:PolicyAvailability; route:'original-payment'|'wallet'|'manual-review'|'unknown'; processingLabel:string; partialRefundSupported:'yes'|'no'|'unknown' }
export interface ChangePolicy { availability:PolicyAvailability; supportedChanges:Array<'date'|'route'|'name-correction'|'room'|'guest-count'|'nights'|'late-arrival'|'early-checkout'>; providerVerificationRequired:boolean }
export interface NoShowPolicy { availability:PolicyAvailability; consequenceLabel:string }
export interface DisruptionPolicy { availability:PolicyAvailability; replacementSupported:'yes'|'no'|'unknown'; refundSupported:'yes'|'no'|'unknown' }
export interface PolicySnapshot { id:string; bookingId:string; version:string; capturedAt:string; sourceLabel:string; serviceType:BookableServiceType; cancellation:CancellationPolicy; refund:RefundPolicy; change:ChangePolicy; noShow:NoShowPolicy; disruption:DisruptionPolicy }
export interface CancellationQuote { id:string; bookingId:string; caseType:AfterSalesCaseType; eligibility:'eligible'|'ineligible'|'unknown'; policyAvailability:PolicyAvailability; deadline?:string; estimatedPenalty?:number; estimatedRefundableAmount?:number; currency:'IRR'; refundRoute:'original-payment'|'wallet'|'manual-review'|'unknown'; providerVerificationRequired:boolean; explanation:string; mock:true }
export interface ChangeQuote { id:string; bookingId:string; caseType:AfterSalesCaseType; changeType:string; eligibility:'eligible'|'ineligible'|'unknown'; priceDifference?:number; fee?:number; currency:'IRR'; providerVerificationRequired:boolean; explanation:string; mock:true }
export interface RefundRequest { id:string; bookingId:string; caseType:AfterSalesCaseType; quoteId:string; status:AfterSalesRequestStatus; createdAt:string; mock:true }
export interface ModificationRequest { id:string; bookingId:string; caseType:AfterSalesCaseType; quoteId:string; status:AfterSalesRequestStatus; requestedChange:string; mock:true }
export interface DisruptionCase { id:string; bookingId:string; source:'provider'|'traveller'|'platform'; status:AfterSalesRequestStatus; replacementOptionsStatus:'unknown'|'available'|'unavailable'; mock:true }
export interface RefundTransaction { id:string; requestId:string; status:'not-created'|'pending'|'completed'|'failed'; amount?:number; authoritative:false }
export interface SupportEscalation { id:string; bookingId:string; reason:'policy-review'|'supplier-issue'|'voucher-issue'|'urgent-travel'|'exceptional-case'|'platform-error'; status:AfterSalesRequestStatus; contextShared:boolean; mock:true }
