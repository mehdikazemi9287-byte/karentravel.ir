# CheckLine bundle — manifest and usage (generated)

Files: 1891 — every file has a status. PRESERVED_AS_REFERENCE 1865, MAPPED 14, IMPLEMENTED 12.
Usage by files: 1.4% of files (26 of 1891) carry content that is implemented or mapped; by bytes 19.1%. The remaining files are the old site code (1,758), evidence and audit documents.
Usage by content records: 10,765 of 23,387 = 46.0% across all content datasets; 10,765 of 21,372 = 50.4% within datasets that are usable at all (excluding BLOCKED and INVALID ones).

## Datasets
| Dataset | Records | Implemented | Status | Note |
|---|---|---|---|---|
| Hotels (location) | 800 | 777 | IMPLEMENTED | 23 held back: 13 without a resolvable country and 9 country/city conflicts (BLOCKED), 1 without a title (INVALID) |
| Hotel descriptions | 621 | 605 | IMPLEMENTED | HTML reduced to text |
| Hotel gallery references | 7,277 | 3,799 | IMPLEMENTED | broken references, byte-identical copies, galleries of non-hotel items and images beyond 12 per hotel are not attached |
| Hotel room rows | 447 | 429 | IMPLEMENTED | hidden rooms and rooms of held-back hotels excluded |
| Hotel facility groups 1–3 (numeric codes) | 586 | 0 | BLOCKED | the code→label lists are site options whose values are not in the bundle; raw codes stay in the bundle, nothing is guessed |
| Hotel coordinates | 0 | 0 | BLOCKED | the source has no latitude/longitude for hotels (75 have a map embed without a text query) |
| Countries | 52 | 50 | IMPLEMENTED | 52 posts are 50 distinct countries (two duplicated in the source) |
| Provinces (state) | 31 | 31 | IMPLEMENTED | matched to existing provinces or added |
| Cities | 109 | 98 | IMPLEMENTED | published cities; drafts/pending, duplicates and ambiguous names are not separate places |
| Tours | 83 | 76 | IMPLEMENTED | 4 trashed and untitled items are INVALID; reference programmes only |
| Tour dates | 165 | 165 | IMPLEMENTED | history only; 3 invalid Jalali dates kept as text |
| Tour ↔ hotel references | 202 | 189 | IMPLEMENTED | references to hotels outside the imported set are dropped; repeated hotels count once per tour |
| Prices, discounts, capacities | 1,320 | 0 | INVALID | historical commercial values (past tours, old discounts): not provable as current, never published; price stays null |
| Visa articles | 5 | 4 | IMPLEMENTED | 1 draft without text is INVALID |
| Country visa notes | 13 | 11 | IMPLEMENTED | notes of duplicated country posts collapse into one |
| Attractions | 12 | 12 | IMPLEMENTED | name, city, coordinates |
| Pages | 82 | 72 | MAPPED | published pages mapped to KarenSeir routes; the bundle has titles and slugs only, no page text |
| Menu items | 69 | 69 | MAPPED | every item resolved to a KarenSeir target (table below) |
| Taxonomy: tour-category | 51 | 51 | IMPLEMENTED | tour search filter |
| Taxonomy: location-category | 39 | 39 | IMPLEMENTED | hotel categories kept on the record; geography expressed by city/country filters |
| Taxonomy: region | 50 | 50 | IMPLEMENTED | kept on the record |
| Taxonomy: city-category | 54 | 54 | IMPLEMENTED | kept on the place |
| Taxonomy: country-category | 14 | 14 | IMPLEMENTED | kept on the place |
| Taxonomy: visa-category | 3 | 3 | IMPLEMENTED | kept on visa content |
| Taxonomy: attraction-category | 2 | 2 | IMPLEMENTED | kept on the venue kind |
| Taxonomy: nav_menu | 7 | 7 | MAPPED | menu table below |
| Taxonomy: category | 37 | 0 | BLOCKED | blog categories; the bundle has no post text |
| Taxonomy: post_tag | 31 | 0 | BLOCKED | blog tags; no post text |
| Taxonomy: term_translations | 27 | 0 | PRESERVED_AS_REFERENCE | translation links of the multilingual plugin |
| Taxonomy: post_translations | 8 | 0 | PRESERVED_AS_REFERENCE | translation links |
| Media library records | 11,152 | 4,132 | IMPLEMENTED | files referenced by imported hotels, rooms, places, tours and attractions; the rest are unreferenced, missing (454) or duplicate copies and stay PRESERVED in the bundle |
| Blog posts | 41 | 0 | BLOCKED | only counted in the bundle; no titles or text were exported |
| Supplier API operations (Citysoft) | 32 | 26 | MAPPED | 26 distinct operations mapped to ports; request/response handling built for flight search and hotel rooms; no live connection |
| Orders, wallet movements, users, roles, options | 0 | 0 | PRESERVED_AS_REFERENCE | audit aggregates without traveller export; not site content |

## Menu items (69; without a target: 0)
| Item | Type | Level | KarenSeir target |
|---|---|---|---|
| صفحه نخست | page | اصلی | `/` |
| تماس با ما | page | اصلی | `/contact` |
| بلاگ | page | اصلی | `/travel-guides` |
| تورها | tour | اصلی | `/tours` |
| هتل ها | location-category | اصلی | `/hotels` |
| مجله گردشگری | page | اصلی | `/travel-guides` |
| جاذبه های گردشگری | page | اصلی | `/attractions` |
| چرا ما را انتخاب می کنید؟ | page | اصلی | `/about` |
| گردشگری سلامت چیست؟ | page | اصلی | `/services` |
| تاژبان گشت پارس | page | اصلی | `/about` |
| اقامت و مهاجرت | page | اصلی | `/visa` |
| صفحه اصلی | page | اصلی | `/` |
| بلاگ | page | اصلی | `/travel-guides` |
| اقامتگاه ها | location-category | اصلی | `/hotels` |
| تور نمایشگاهی | page | زیرمنو | `(صفحهٔ منتشرنشده در منبع)` |
| تور اسپانیا | tour-category | زیرمنو | `/tours/destination/es` |
| مسقط | tour-category | زیرمنو | `/tours/destination/om` |
| تور ترکیه | page | زیرمنو | `/tours/search?destination=tr` |
| تور کوش آداسی | tour-category | زیرمنو | `/tours/destination/tr-kusadas` |
| تور استانبول | tour-category | زیرمنو | `/tours/destination/tr-istanbul` |
| تور آنتالیا | tour-category | زیرمنو | `/tours/destination/tr-antalya` |
| تور دبی | tour-category | زیرمنو | `/tours/destination/ae-dubai` |
| تور گرجستان | tour-category | زیرمنو | `/tours/destination/ge` |
| صفحه اصلی | page | اصلی | `/` |
| اصفهان | tour-category | زیرمنو | `/tours/destination/ir-isfahan` |
| شیراز | tour-category | زیرمنو | `/tours/destination/ir-shiraz` |
| قشم | tour-category | زیرمنو | `/tours/destination/cl-city-12979` |
| کیش | tour-category | زیرمنو | `/tours/destination/cl-city-224` |
| گیلان | tour-category | زیرمنو | `/tours/destination/cl-city-6829` |
| مازندران | tour-category | زیرمنو | `/tours/destination/cl-city-6849` |
| تور مشهد | tour-category | زیرمنو | `/tours/destination/ir-mashhad` |
| تورهای داخلی | tour-category | زیرمنو | `/tours/search?category=تورهای داخلی` |
| تور خارجی | tour-category | زیرمنو | `/tours/search?category=تور خارجی` |
| تور ارمنستان | tour-category | زیرمنو | `/tours/destination/am` |
| تور برزیل | tour-category | زیرمنو | `/tours/destination/br` |
| تور سریلانکا | tour-category | زیرمنو | `/tours/destination/lk` |
| تور عمان | tour-category | زیرمنو | `/tours/destination/om` |
| تور تایلند | tour-category | زیرمنو | `/tours/destination/th` |
| تور ازمیر | tour-category | زیرمنو | `/tours/destination/tr-izmir` |
| تور مارماریس | tour-category | زیرمنو | `/tours/destination/tr-marmaris` |
| تور | tour-category | اصلی | `/tours/search?category=تور` |
| تور چین | tour-category | زیرمنو | `/tours/destination/cn` |
| تور روسیه | tour-category | زیرمنو | `/tours/destination/ru` |
| تور ژاپن | tour-category | زیرمنو | `/tours/destination/jp` |
| تور مالزی | tour-category | زیرمنو | `/tours/destination/my` |
| تور هند | tour-category | زیرمنو | `/tours/destination/in` |
| تور یونان | tour-category | زیرمنو | `/tours/destination/gr` |
| تور زیارتی | tour-category | زیرمنو | `/tours/search?category=تور زیارتی` |
| تور کربلا | tour-category | زیرمنو | `/tours/destination/iq-karbala` |
| تور مشهد | tour-category | زیرمنو | `/tours/destination/ir-mashhad` |
| قوانین و مقررات | page | اصلی | `/terms` |
| هتل | location-category | اصلی | `/hotels` |
| هتل های آسیا | location-category | زیرمنو | `/hotels` |
| هتل های ایران | location-category | زیرمنو | `/hotels?country=IR` |
| هتل های ارمنستان | location-category | زیرمنو | `/hotels?country=AM` |
| هتل های عراق | location-category | زیرمنو | `/hotels?country=IQ` |
| هتل های ترکیه | location-category | زیرمنو | `/hotels?country=TR` |
| هتل های دبی | location-category | زیرمنو | `/hotels?country=AE&city=ae-dubai` |
| هتل های گرجستان | location-category | زیرمنو | `/hotels?country=GE` |
| هتل های ازمیر | location-category | زیرمنو | `/hotels?country=TR&city=tr-izmir` |
| هتل های استانبول | location-category | زیرمنو | `/hotels?country=TR&city=tr-istanbul` |
| هتل های تایلند | location-category | زیرمنو | `/hotels?country=TH` |
| هتل های آفریقا | location-category | زیرمنو | `/hotels` |
| هتل های اروپا | location-category | زیرمنو | `/hotels` |
| هتل‌های آمریکا و اقیانوسیه | location-category | زیرمنو | `/hotels` |
| درباره ما | page | اصلی | `/about` |
| اپلیکیشن چک‌لاین تراول | page | اصلی | `/` |
| اپلیکیشن چک‌لاین تراول | page | اصلی | `/` |
| اپلیکیشن چک‌لاین تراول | page | اصلی | `/` |

## Old pages
| Old path | Title | In menu | KarenSeir target |
|---|---|---|---|
| `/bsi-tour/` | bsi tour |  | `/tours/search` |
| `/flight/` | flight |  | `/flights` |
| `/hotel/` | hotel |  | `/hotels` |
| `/tour/` | tour |  | `/tours/search` |
| `/visa/` | visa |  | `/visa` |
| `/اقامت-و-مهاجرت/` | اقامت و مهاجرت | yes | `/visa` |
| `/اپلیکیشن-چکلاین-تراول/` | اپلیکیشن چک‌لاین تراول | yes | `/` |
| `/blog/` | بلاگ | yes | `/travel-guides` |
| `/abouttazhban/` | تاژبان گشت پارس | yes | `/about` |
| `/تفریحات-کیش/` | تفریحات کیش |  | `/attractions` |
| `/contact/` | تماس با ما | yes | `/contact` |
| `/تور/` | تور |  | `/tours/search?destination=iq-tahrawa` |
| `/تور-آنتالیا/` | تور آنتالیا |  | `/tours/search?destination=tr-antalya` |
| `/تور-ارمنستان/` | تور ارمنستان |  | `/tours/search?destination=am` |
| `/hotel-tabriz/` | تور استانبول |  | `/tours/search?destination=tr-istanbul` |
| `/تور-اسپانیا/` | تور اسپانیا |  | `/tours/search?destination=es` |
| `/تور-برزیل-2/` | تور برزیل |  | `/tours/search?destination=br` |
| `/تور-برزیل/` | تور برزیل |  | `/tours/search?destination=br` |
| `/تور-تایلند/` | تور تایلند |  | `/tours/search?destination=th` |
| `/تور-ترکیه/` | تور ترکیه |  | `/tours/search?destination=tr` |
| `/تور-ترکیه-2/` | تور ترکیه | yes | `/tours/search?destination=tr` |
| `/تور-خارجی/` | تور خارجی |  | `/tours/search` |
| `/domestic-tour/` | تور داخلی |  | `/tours/search` |
| `/تور-دبی/` | تور دبی |  | `/tours/search?destination=ae-dubai` |
| `/تور-روسیه/` | تور روسیه |  | `/tours/search?destination=ru` |
| `/تور-سریلانکا/` | تور سریلانکا |  | `/tours/search?destination=lk` |
| `/iraqtours/` | تور عراق |  | `/tours/search?destination=iq` |
| `/arabiatours/` | تور عربستان |  | `/tours/search?destination=sa` |
| `/عمان/` | تور عمان |  | `/tours/search?destination=om` |
| `/تور-نمایشگاهی/` | تور نمایشگاهی |  | `/tours/search` |
| `/تور-های-چند-روزه/` | تور های چند روزه |  | `/tours/search` |
| `/تور-های-یک-روزه/` | تور های یک روزه |  | `/tours/search` |
| `/تور-ژاپن/` | تور ژاپن |  | `/tours/search?destination=jp` |
| `/تور-گرجستان/` | تور گرجستان |  | `/tours/search?destination=ge` |
| `/تور-یک-روزه-لفور/` | تور یک روزه لفور |  | `/tours/search` |
| `/تور-یک-روزه-ماسوله-و-قلعه-رودخان/` | تور یک روزه ماسوله |  | `/tours/search` |
| `/تور-های-یک-روزه-2/` | تور یک روزه نمک آبرود |  | `/tours/search` |
| `/تور-یک-روزه-نمک-آبرود/` | تور یک روزه نمک آبرود |  | `/tours/search` |
| `/تورهای-ویژه-bsi/` | تورهای ویژه BSI |  | `/tours/search` |
| `/توریسم-درمانی/` | توریسم درمانی |  | `/tours/search` |
| `/ثبت-شکایت/` | ثبت شکایت |  | `/support` |
| `/ثبت-شکایت-2/` | ثبت شکایت |  | `/support` |
| `/راهنمای-خرید-بلیط-پرواز-خارجی/` | جاذبه های گردشگری | yes | `/attractions` |
| `/about/` | درباره ما | yes | `/about` |
| `/راهنمای-خرید-هتل/` | راهنمای خرید هتل |  | `/hotels` |
| `/رزرو-هتل-خارجی/` | رزرو هتل خارجی |  | `/hotels` |
| `/صفحه-اصلی/` | صفحه اصلی | yes | `/` |
| `/صفحه-اصلی-المانی/` | صفحه اصلی المانی |  | `/` |
| `/صفحه-اصلی-انگلیسی/` | صفحه اصلی انگلیسی |  | `/` |
| `/صفحه-اصلی-ترکی/` | صفحه اصلی ترکی |  | `/` |
| `/صفحه-اصلی-عربی/` | صفحه اصلی عربی |  | `/` |
| `/صنایع-دستی/` | صنایع دستی |  | `/handicrafts` |
| `/site-rules/` | قوانین و مقررات | yes | `/terms` |
| `/شرایط-استرداد-پرواز-خارجی/` | مجله گردشگری |  | `/travel-guides` |
| `/مجله-گردشگری/` | مجله گردشگری | yes | `/travel-guides` |
| `/مشاوره-گردشگری-آنلاین/` | مشاوره گردشگری آنلاین |  | `/support` |
| `/هتل-های-اردبیل/` | هتل های اردبیل |  | `/hotels?country=IR&city=ir-ardabil` |
| `/هتل-های-ارمنستان/` | هتل های ارمنستان |  | `/hotels?country=AM` |
| `/هتل-های-اصفهان/` | هتل های اصفهان |  | `/hotels?country=IR&city=ir-isfahan` |
| `/هتل-های-امارات/` | هتل های امارات |  | `/hotels` |
| `/iranht/` | هتل های ایران |  | `/hotels?country=IR` |
| `/هتل-های-تبریز/` | هتل های تبریز |  | `/hotels?country=IR&city=cl-city-6803` |
| `/هتل-های-تهران/` | هتل های تهران |  | `/hotels?country=IR&city=cl-city-3322` |
| `/هتل-های-رشت/` | هتل های رشت |  | `/hotels?country=IR&city=ir-rasht` |
| `/هتل-های-شیراز/` | هتل های شیراز |  | `/hotels?country=IR&city=ir-shiraz` |
| `/هتل-های-مشهد/` | هتل های مشهد |  | `/hotels?country=IR&city=ir-mashhad` |
| `/هتل-های-کیش/` | هتل های کیش |  | `/hotels?country=IR&city=cl-city-224` |
| `/هتل-های-گرجستان/` | هتل های گرجستان |  | `/hotels?country=GE` |
| `/هتل-های-یزد/` | هتل های یزد |  | `/hotels?country=IR&city=cl-city-8609` |
| `/چرا-ما-را-انتخاب-کنید؟/` | چرا ما را انتخاب می کنید؟ | yes | `/about` |
| `/کشور/` | کشور |  | `/destinations` |
| `/گردشگری-سلامت/` | گردشگری سلامت چیست؟ | yes | `/services` |

## Screens of the audit → KarenSeir
| Id | Screen | Role | KarenSeir |
|---|---|---|---|
| D01 | خانه و ناوبری | مشتری | `/` |
| D02 | جست‌وجوی پرواز | مشتری/همکار | `/flights` |
| D03 | نتایج پرواز | مشتری | `/search/results?vertical=flight` |
| D04 | جزئیات نرخ | مشتری/هواپیمایی | `/search/results (fare detail)` |
| D05 | جست‌وجوی اقامت | مشتری | `/hotels` |
| D06 | فهرست و نقشه اقامت | مشتری | `/hotels (list; map view not built)` |
| D07 | صفحه هتل | مشتری | `/hotels/[slug]` |
| D08 | صفحه تور | مشتری | `/tours/[slug]` |
| D09 | پرونده زیارتی | مشتری/مدیر | `— (no pilgrimage vertical)` |
| D10 | فرم مسافران | مشتری/همکار | `/checkout (travellers step)` |
| D11 | بازبینی سفارش | مشتری | `/checkout` |
| D12 | پرداخت و بازگشت | مشتری | `/payments` |
| D13 | مدیریت سفر | مشتری | `/trips, /manage-booking` |
| D14 | تغییر و استرداد | مشتری/اپراتور | `/manage-booking (service requests)` |
| D15 | کیف پول | مشتری/همکار | `/account (wallet)` |
| D16 | پنل همکار | آژانس | `/agency` |
| D17 | پنل شریک | شریک تجاری | `/white-label` |
| D18 | پنل تأمین | هتل/تأمین‌کننده | `/supplier` |
| D19 | صف صدور | مدیر هواپیمایی | `— (needs a flight supplier)` |
| D20 | عملیات تور | مدیر تور | `/admin/tours, /supplier (tours)` |
| D21 | عملیات زیارتی | مدیر زیارتی | `—` |
| D22 | عملیات خدمات | مدیر خدمات | `/backoffice` |
| D23 | میز پشتیبانی | پشتیبانی | `/backoffice/support` |
| D24 | تطبیق مالی | مالی | `/finance` |
| D25 | تسویه تأمین/همکار | مالی/خزانه | `/finance/accounting, /supplier/settlements` |
| D26 | صورتحساب مالیاتی | مدیر مالیاتی | `/finance/accounting (tax summary only)` |
| D27 | مدیریت کاتالوگ | مدیر محتوا | `/admin/catalog` |
| D28 | نگاشت تأمین‌کننده | مدیر محصول | `/admin/catalog (mapping editor), /supplier/hotels` |
| D29 | قوانین قیمت و اعتبار | بازرگانی/مالی | `— (pricing rules have no screen)` |
| D30 | نقش و دسترسی | امنیت/مدیر tenant | `/admin` |
| D31 | سلامت سرویس‌ها | عملیات | `/integrations` |
| D32 | گزارش مدیران | مدیر ارشد | `— (no executive report screen)` |
| D33 | تنظیمات اتصال | مدیر فنی محدود | `/integrations` |
| D34 | مرکز اسناد | مشتری/عملیات | `/trips/[id] (voucher/documents)` |
| D35 | لاگ ممیزی | حسابرس | `/admin/catalog history, audit_events (no global screen)` |

## Roles of the audit → KarenSeir roles
| Id | Role | KarenSeir |
|---|---|---|
| U01 | مهمان | anonymous |
| U02 | مشتری حقیقی | customer |
| U03 | خریدار شرکتی | employee / organization_admin |
| U04 | همکار فروش | agency_partner |
| U05 | مدیر آژانس همکار | agency_partner (+ membership) |
| U06 | شریک تجاری | tenant_admin (white-label) |
| U07 | تأمین‌کننده | supplier |
| U08 | مدیر اقامت | supplier (hotel) / backoffice_expert |
| U09 | مدیر تور | supplier (tour) / backoffice_expert |
| U10 | مدیر زیارتی | — (no pilgrimage role) |
| U11 | مدیر هواپیمایی | — (no flight-operations role) |
| U12 | مدیر خدمات | backoffice_expert |
| U13 | کارشناس پشتیبانی | backoffice_expert (support:manage) |
| U14 | مدیر پشتیبانی | backoffice_expert |
| U15 | کارشناس مالی | finance_operator |
| U16 | مدیر مالی | finance_operator |
| U17 | خزانه‌دار | finance_operator (settlement:manage) |
| U18 | مدیر مالیاتی | — (no tax role) |
| U19 | مدیر کاتالوگ | backoffice_expert / platform_admin (catalog) |
| U20 | مدیر محصول/بازرگانی | tenant_admin |
| U21 | مدیر امنیت و زیرساخت | platform_admin |
| U22 | حسابرس و مدیر ارشد | — (read-only auditor role not defined) |

## Service registry → verticals
| Registry | Service | Active | KarenSeir |
|---|---|---|---|
| cn | flight | 1 | `/flights` |
| cn | hotel | 1 | `/hotels` |
| cn | flighandhotel | 1 | `/search (پرواز + هتل)` |
| cn | tour | 0 | `/tours` |
| cn | package | 0 | `/search (package)` |
| cn | cip | 1 | `— (no CIP vertical; Citysoft /cip mapped in the contract)` |
| cn | insurance | 0 | `— (contract only)` |
| cn | visa | 0 | `/visa` |
| cn | train | 0 | `/trains` |
| en_cn | flight | 1 | `/flights` |
| en_cn | hotel | 1 | `/hotels` |
| en_cn | flighandhotel | 1 | `/search (پرواز + هتل)` |
| en_cn | tour | 0 | `/tours` |
| en_cn | package | 0 | `/search (package)` |
| en_cn | cip | 0 | `— (no CIP vertical; Citysoft /cip mapped in the contract)` |
| en_cn | insurance | 0 | `— (contract only)` |
| ar_cn | flight | 1 | `/flights` |
| ar_cn | hotel | 1 | `/hotels` |
| ar_cn | flighandhotel | 1 | `/search (پرواز + هتل)` |
| ar_cn | tour | 0 | `/tours` |
| ar_cn | package | 0 | `/search (package)` |
| ar_cn | cip | 0 | `— (no CIP vertical; Citysoft /cip mapped in the contract)` |
| ar_cn | insurance | 0 | `— (contract only)` |
