# Trip Assistant Specification

دستیار گفت‌وگویی نیاز، زمان، مبدا/مقصد، بودجه، نفرات و ترجیح را جمع می‌کند؛ itinerary ترکیبی پرواز/قطار/اقامت/تور/خودرو/بیمه/تجربه می‌سازد، policy سازمان را اعمال و دلیل پیشنهاد را بیان می‌کند. برنامه ذخیره/اشتراک/ارسال approval و همراهی پیش/حین/پس از سفر دارد.

LLM فقط intent، explanation و orchestration انجام می‌دهد. قیمت، ظرفیت، قانون، eligibility و approval از ابزارهای authoritative خوانده می‌شوند؛ نبود ابزار معتبر به پاسخ «قابل استعلام نیست» ختم می‌شود. guardrail: PII minimization، policy check، human handoff، trace و feedback.

Prototype فقط نمای گفتگو و نقشه مسیر است و هیچ اتصال AI یا نرخ زنده را ادعا نمی‌کند.
