"""Stored accommodation rates; no invented inventory or provider responses."""
from datetime import date, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROPERTY_TYPES = ('hotel', 'villa', 'apartment', 'furnished_apartment', 'suite', 'ecolodge',
                  'cabin', 'rural', 'rural_house', 'coastal', 'beach_property', 'forest',
                  'forest_property', 'pool_property', 'traditional_house', 'resort',
                  'hostel', 'camp', 'special_stay', 'mountain')

class CalendarDay(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['AVAILABLE', 'UNAVAILABLE'] = 'AVAILABLE'
    nightly_price: int | None = Field(default=None, gt=0)
    minimum_stay: int | None = Field(default=None, ge=1, le=365)

class Season(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: str
    end: str
    nightly_price: int = Field(gt=0)

    @model_validator(mode='after')
    def valid_dates(self):
        for value in (self.start, self.end):
            parsed = date.fromisoformat('2000-' + value)
            if parsed.strftime('%m-%d') != value:
                raise ValueError('Use MM-DD seasonal dates')
        return self

class StayRates(BaseModel):
    model_config = ConfigDict(extra='forbid')
    min_stay: int = Field(default=1, ge=1, le=365)
    weekend_days: list[int] = Field(default_factory=lambda: [3, 4], max_length=7)
    weekend_price: int | None = Field(default=None, gt=0)
    seasonal_rates: list[Season] = Field(default_factory=list, max_length=50)
    base_capacity: int | None = Field(default=None, ge=1, le=100)
    extra_guest_price: int = Field(default=0, ge=0)
    cleaning_fee: int = Field(default=0, ge=0)
    service_fee: int = Field(default=0, ge=0)
    calendar: dict[date, CalendarDay] = Field(default_factory=dict, max_length=730)

    @model_validator(mode='after')
    def valid_weekdays(self):
        if any(day < 0 or day > 6 for day in self.weekend_days):
            raise ValueError('Weekday must be 0..6')
        if self.extra_guest_price and self.base_capacity is None:
            raise ValueError('Extra guest price requires base capacity')
        return self


def nightly_rate(rates: StayRates, base: int, day: date) -> tuple[int, str, int, str]:
    override = rates.calendar.get(day)
    minimum = override.minimum_stay if override and override.minimum_stay else rates.min_stay
    if override and override.nightly_price:
        return override.nightly_price, 'special', minimum, override.status
    for season in rates.seasonal_rates:
        md = day.strftime('%m-%d')
        if (season.start <= md <= season.end) if season.start <= season.end else (md >= season.start or md <= season.end):
            return season.nightly_price, 'seasonal', minimum, override.status if override else 'AVAILABLE'
    if rates.weekend_price and day.weekday() in rates.weekend_days:
        return rates.weekend_price, 'weekend', minimum, override.status if override else 'AVAILABLE'
    return base, 'base', minimum, override.status if override else 'AVAILABLE'


def stay_price(rates: StayRates, *, base: int, capacity: int, guests: int, arrival: date, departure: date, currency: str) -> dict:
    nights = (departure-arrival).days
    if nights < 1 or nights > 365 or guests < 1 or guests > capacity:
        raise ValueError('بازه یا ظرفیت اقامت معتبر نیست')
    if rates.base_capacity and rates.base_capacity > capacity:
        raise ValueError('ظرفیت پایه با ظرفیت واحد سازگار نیست')
    breakdown = []
    minimum = rates.min_stay
    for offset in range(nights):
        day = arrival + timedelta(days=offset)
        amount, source, day_minimum, state = nightly_rate(rates, base, day)
        minimum = max(minimum, day_minimum)
        if state == 'UNAVAILABLE':
            raise ValueError('اقامت در یکی از تاریخ‌های انتخاب‌شده قابل رزرو نیست')
        breakdown.append({'date': day.isoformat(), 'nightly_price': amount, 'rate_source': source})
    if nights < minimum:
        raise ValueError(f'حداقل اقامت در این بازه {minimum} شب است')
    accommodation = sum(n['nightly_price'] for n in breakdown)
    extra = max(0, guests-(rates.base_capacity or capacity))*rates.extra_guest_price*nights
    fees = {'accommodation': accommodation, 'extra_guests': extra,
            'cleaning': rates.cleaning_fee, 'service': rates.service_fee}
    return {'total_amount': sum(fees.values()), 'nights': nights, 'min_stay': minimum,
            'currency': currency, 'nightly_breakdown': breakdown, 'price_components': fees}
