"""Fixed-stay manual allotments. Never infer rate or occupancy terms."""
from datetime import date
from typing import Literal, Annotated
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class HotelRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adults: int = Field(strict=True, ge=1, le=20)
    children_ages: list[Annotated[int, Field(strict=True)]] = Field(default_factory=list, max_length=19)

    @model_validator(mode="after")
    def ages(self):
        if any(type(age) is not int or not 0 <= age <= 17 for age in self.children_ages):
            raise ValueError("سن کودک باید عدد صحیح بین صفر و ۱۷ باشد")
        self.children_ages = sorted(self.children_ages)
        return self


class HotelStay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_in: date
    check_out: date
    rooms: list[HotelRoom] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def dates_and_party(self):
        if self.check_out <= self.check_in:
            raise ValueError("تاریخ خروج باید بعد از ورود باشد")
        if sum(r.adults + len(r.children_ages) for r in self.rooms) > 20:
            raise ValueError("رزرو بیش از ۲۰ مهمان نیازمند هماهنگی گروهی است")
        return self


class HotelRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_in: date
    check_out: date
    room_type: str = Field(min_length=1, max_length=160)
    rate_plan: str = Field(min_length=1, max_length=160)
    price_basis: Literal["room_stay"]
    occupancy: HotelRoom


def validate_hotel_stay(attributes: dict, stay: HotelStay | None, units: int) -> dict:
    try:
        rate = HotelRate.model_validate(attributes.get("hotel_rate"))
    except ValidationError:
        raise HTTPException(409, "تاریخ، نرخ و ظرفیت اتاق از منبع عرضه مشخص نشده است؛ با پشتیبانی تماس بگیرید")
    if stay is None:
        raise HTTPException(422, "تاریخ اقامت و ترکیب مهمانان هر اتاق را مشخص کنید")
    if stay.check_in < date.today() or (stay.check_in, stay.check_out) != (rate.check_in, rate.check_out):
        raise HTTPException(409, "این نرخ برای تاریخ اقامت انتخاب‌شده معتبر نیست")
    if len(stay.rooms) != units or any(room != rate.occupancy for room in stay.rooms):
        raise HTTPException(409, "تعداد اتاق یا ترکیب مهمانان با شرایط این نرخ تطابق ندارد")
    return stay.model_dump(mode="json")


def validate_hotel_rate(attributes: dict) -> None:
    try:
        rate = HotelRate.model_validate(attributes.get("hotel_rate"))
        stay = HotelStay(check_in=rate.check_in, check_out=rate.check_out, rooms=[rate.occupancy])
    except ValidationError:
        raise HTTPException(422, "تاریخ و ترکیب مهمانان نرخ اتاق معتبر نیست")
    validate_hotel_stay(attributes, stay, 1)
