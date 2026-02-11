# Data Extraction FAQ

## Чому кількість оголошень з бюджетом в базі не співпадає з симуляцією?

### Питання

Запит до бази показує 174 оголошення з бюджетом:
```sql
SELECT COUNT(DISTINCT ad_id)
FROM analytics_reports.spendings_distributed
WHERE operationdate = '2026-02-01'
  AND country_id = 13
  AND category_id = 1361
  AND price_per_day > 0
```

Але симуляція каже: "99 ads with budget"

Різниця: 174 - 99 = **75 оголошень**. Чому?

### Відповідь

Це **правильна поведінка**. Система створює Ad objects тільки для оголошень які **мають impressions** (reach).

75 оголошень з бюджетом БЕЗ impressions = це:
- 🚫 **Заблоковані користувачі** - їх оголошення не деактивуються, але приховуються з показів
- 🚫 **Приховані оголошення** - з інших причин (модерація, тимчасове приховування)
- 🚫 **Технічні записи** - можуть мати budget record але не показуватись

**Бізнес логіка**: Якщо оголошення не отримувало impressions вчора → воно не має брати участь в аукціоні сьогодні.

### Перевірка

Щоб перевірити які саме оголошення не мають impressions:

```sql
-- 1. Отримай список ad_id з бюджетом
SELECT DISTINCT ad_id
FROM analytics_reports.spendings_distributed
WHERE operationdate = '2026-02-01'
  AND country_id = 13
  AND category_id = 1361
  AND price_per_day > 0
ORDER BY ad_id;
-- Результат: 174 оголошення

-- 2. Отримай список ad_id з impressions
SELECT DISTINCT ad_id
FROM analytics.enriched_distributed
WHERE data_chunk_date >= toDate('2026-02-01')
  AND data_chunk_date <= toDate('2026-02-01')
  AND toDate(timestamp) >= toDate('2026-02-01')
  AND toDate(timestamp) <= toDate('2026-02-01')
  AND country_id = 13
  AND category_id = 1361
  AND component = 'listing'
  AND screen != 'my_profile'
  AND element = 'ad'
  AND action = 'view'
  AND feed_id IN ('6500', '6002')
  AND client != 'backend'
  AND ad_id IS NOT NULL
  AND user_id IS NOT NULL
ORDER BY ad_id;
-- Результат: ~7800 оголошень

-- 3. Порівняй списки за допомогою Python скрипту або вручну
```

### Очікувані метрики

Для типової категорії:
- **Всього оголошень з бюджетом**: 150-200
- **З них мають impressions**: 60-70% (активні оголошення)
- **З них БЕЗ impressions**: 30-40% (заблоковані/приховані)

### Чи це проблема?

**Ні, це правильно.** Система коректно фільтрує:
1. ✅ Витягує ВСІ бюджети з `spendings_distributed` (174)
2. ✅ Витягує ВСІ impressions з `enriched_distributed` (7800)
3. ✅ Створює Ad objects тільки для перетину (99)
4. ✅ Оголошення без impressions не беруть участь в аукціоні

### Logging

Симуляція логує:
```
Initialized 7800 ads
Reset budgets for 2026-02-01: 99 ads with budget, total=11245.0 kopecks
```

Різниця між 7800 (total ads) і 99 (ads with budget) = нормально.
Це означає що 7701 оголошень беруть участь як organic (без бюджету).

### Якщо потрібно дізнатись більше

Щоб побачити конкретні ad_id які не беруть участь:
```python
# Використай Python скрипт для порівняння CSV експортів
# Скрипт: /tmp/compare_ads.py
python3 /tmp/compare_ads.py
```

## Чому `spendings_distributed` має більше записів ніж унікальних ad_id?

### Питання

```sql
SELECT
    COUNT(*) as total_records,              -- 200 записів
    COUNT(DISTINCT ad_id) as unique_ads     -- 174 унікальних ad_id
FROM analytics_reports.spendings_distributed
WHERE ...
```

Чому різниця?

### Відповідь

Одне оголошення може мати **кілька campaign_id** на одну дату:
- Кампанія була зупинена і перезапущена → new campaign_id
- Бюджет був змінений → new campaign_id
- Технічні оновлення → new campaign_id

**Деduplікація**: Система автоматично вибирає **останню кампанію** (найбільший campaign_id):

```python
# data_extraction.py:365-366
df = df.sort_values(['ad_id', 'date', 'campaign_id'], ascending=[True, True, False])
df = df.drop_duplicates(subset=['ad_id', 'date'], keep='first')
```

Після деduplікації: 200 records → 174 unique ads.

## Чому симуляція витягує менше бюджету ніж показує DBeaver?

### Сценарій

DBeaver query:
```sql
SELECT SUM(price_per_day) / 100 FROM spendings_distributed
WHERE category_id = 1361 AND operationdate = '2026-02-01'
-- Результат: 240 AZN
```

Симуляція:
```
Total Budget: 139.20 AZN
```

Різниця: 240 - 139.20 = **100.8 AZN** (42%)

### Причина (раніше - до з'ясування)

**Старий код** використовував subquery фільтр:
```python
AND ad_id GLOBAL IN (
    SELECT DISTINCT ad_id FROM enriched_distributed WHERE ...
)
```

Це виключало оголошення БЕЗ impressions з витягування бюджетів.

### Поточний стан

**Після з'ясування**: Різниця 100.8 AZN = бюджети заблокованих користувачів.

Система **коректно** не включає їх в симуляцію, тому що:
1. ✅ Вони не мають impressions (заблоковані)
2. ✅ Не мають брати участь в аукціоні
3. ✅ Їх бюджети не мають витрачатись

**Рішення**: Немає проблеми. Поведінка правильна.

### Якщо різниця > 50%

Якщо різниця дуже велика (>50%), можливі причини:
- Масове блокування користувачів в категорії
- Технічні проблеми з показами (перевір feed_id фільтри)
- Категорія має багато тестових/прихованих оголошень

Перевір у відділі модерації / безпеки.

## Чому в симуляції більше paid ads/sellers ніж в actual data?

**🏷️ Теги:** `reporting`, `budget-driven-eligibility`, `cold-start`, `feed_id`, `scope`

**❓ Питання:**
В summary statistics бачу:
```
Sellers with Reach:
  Actual:    Paid sellers: 99
  Simulated: Paid sellers: 141  ← На 42 більше!

Ads with Reach:
  Actual:    Paid ads: 141
  Simulated: Paid ads: 208  ← На 67 більше!
```

Чому в симуляції більше paid ads/sellers ніж було в actual data?

**💡 Коротка відповідь:**
Це очікувана поведінка після впровадження budget-driven eligibility. Simulated рахує ВСІ ads з budget (включно з cold-start), а actual рахує тільки ads з budget ТА з historical reach в обраному scope.

**📚 Детальна відповідь:**

### Причина розбіжності

**Actual paid ads/sellers** (як рахується):
```python
# reporting.py:518-521
ads_paid_actual = ad_comparison[
    (ad_comparison['actual_reach_total'] > 0) &  # ← Треба мати historical reach!
    (ad_comparison['is_paid_actual'] == True)
].shape[0]
```
- Рахуються тільки ads з budget **ТА** з historical reach в обраному scope
- Scope визначається фільтром: `feed_id IN ('6500', '6002')`
- Якщо ad мав budget але всі його impressions були з інших feed_id → він **НЕ** вважається paid в actual

**Simulated paid ads/sellers** (як рахується):
```python
# reporting.py:428-429, 525-528
paid_ad_ids = set(budgets_df[budgets_df['daily_budget'] > 0]['ad_id'].unique())

ads_paid_simulated = sim_results_dedup[
    (sim_results_dedup['simulated_reach'] > 0) &
    (sim_results_dedup['ad_id'].isin(paid_ad_ids))  # ← ВСІ з budget!
].shape[0]
```
- Рахуються **ВСІ** ads з budget (незалежно від historical reach)
- Budget-driven eligibility дозволяє cold-start ads брати участь в аукціоні
- Ці ads можуть виграти reach в симуляції навіть без historical data в scope

### Приклад

```
Ad 12345:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Budget allocated:           50 AZN ✅
Historical impressions:     1000 (але всі з feed_id='9999')
Historical reach в scope:   0 ❌ (бо feed_id='6500'/'6002' = 0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Як рахується:
┌───────────┬────────────────────────────────────────────┐
│ Actual    │ Paid = FALSE                               │
│           │ (бо actual_reach_total = 0 в scope)        │
├───────────┼────────────────────────────────────────────┤
│ Simulated │ Paid = TRUE                                │
│           │ (є budget + виграв 120 reach в аукціоні)  │
└───────────┴────────────────────────────────────────────┘
```

### Чому в базі такі дані?

Ads можуть отримувати impressions з різних джерел (feed_id):

| feed_id | Опис | Приклад |
|---------|------|---------|
| `6500` | Основний feed (Android) | Listings в мобільному додатку |
| `6002` | Додатковий feed (iOS/Web) | Listings на вебсайті |
| `9999` | Legacy feed | Старі записи до міграції |
| `7001` | Тестовий feed | A/B тестування нових features |

**Типові сценарії:**

1. **Новий ad (cold-start)**
   ```
   Day 1: Budget allocated, no impressions yet
   Day 2: Simulation включає його в аукціон
          ↓
   Result: Simulated paid = TRUE, Actual paid = FALSE
   ```

2. **Migration між feed_id**
   ```
   Week 1: Ad показувався в feed_id='9999' (legacy)
   Week 2: Переключено на feed_id='6500' (основний)
           ↓
   Historical data: Всі impressions з '9999' (поза scope)
   Simulation scope: Тільки '6500'/'6002'
           ↓
   Result: Simulated paid = TRUE, Actual paid = FALSE
   ```

3. **A/B testing**
   ```
   Ad був в тестовій групі (feed_id='7001')
   Тепер запущений в production (feed_id='6500')
           ↓
   Result: Є budget, але немає historical reach в production scope
   ```

4. **Budget allocation без активації**
   ```
   Seller виділив бюджет, але:
   - Ad не пройшов модерацію
   - Ad тимчасово деактивований
   - Технічні проблеми з показами
           ↓
   Result: Є budget record, але немає impressions
   ```

### Чи це проблема?

**НІ!** Це feature, не bug:

✅ **Budget-driven eligibility** - правильна поведінка:
- Ads з budget мають **право** брати участь в аукціоні
- Cold-start ads отримують **шанс** конкурувати
- Симуляція **більш inclusive** ніж historical data

✅ **Production-ready**:
- Заміна поточного алгоритму на budget-driven
- Фокус на забезпеченні можливості участі для всіх платних ads
- Справедлива конкуренція для нових ads

### Як читати звіт

```
Ads with Reach:
  Actual:    141 paid ads (тільки з historical reach в scope)
  Simulated: 208 paid ads (включає 67 cold-start ads)
             ↑
             +67 ads отримали шанс завдяки budget-driven eligibility
```

**Розшифровка:**
- `141` = ads з budget які **мали** historical reach в scope (`feed_id='6500'/'6002'`)
- `208` = **ВСІ** ads з budget (незалежно від historical reach)
- `208 - 141 = 67` = кількість cold-start ads які:
  - Мали budget ✅
  - НЕ мали historical reach в обраному scope ❌
  - Виграли reach в симуляції через новий алгоритм ✅

### Додаткові метрики для перевірки

Дивіться секцію **Paid Coverage Analysis** для точних цифр:

```
Paid Coverage Analysis:
  Paid Ads:
    Total:          151  ← Всі ads з budget в period
    With Reach:     151  ← Скільки отримали reach в симуляції
    Coverage:       100% ← Відсоток успішної участі
```

**Інтерпретація:**
- `Total: 151` - всі ads які мали budget хоча б 1 день в періоді
- `With Reach: 151` - всі з них успішно виграли хоча б 1 impression
- `Coverage: 100%` - жоден paid ad не залишився без reach

**💻 Код:**

```python
# Локація: reporting.py:426-446
# Task 5.3: Create period-level paid flags (not last-day state)
# An ad is "paid" if it had budget > 0 on ANY day in the period
paid_ad_ids = set(budgets_df[budgets_df['daily_budget'] > 0]['ad_id'].unique())
paid_seller_ids = set(budgets_df[budgets_df['daily_budget'] > 0]['seller_id'].unique())

# Task 5.4: Deduplicate simulation_results by ad_id
sim_results_dedup = simulation_results.drop_duplicates(subset=['ad_id'])

# Count paid sellers/ads with simulated reach > 0 (using period-level flags)
paid_ads_with_reach_df = sim_results_dedup[
    (sim_results_dedup['ad_id'].isin(paid_ad_ids)) &
    (sim_results_dedup['simulated_reach'] > 0)
]
paid_sellers_with_reach = paid_ads_with_reach_df['seller_id'].nunique()
paid_ads_with_reach = paid_ads_with_reach_df['ad_id'].nunique()
```

```python
# Локація: data_extraction.py:321-336
# Task 1.2: Removed impression-presence dependency
query = f"""
SELECT
    ad_id, user_id as seller_id, category_id,
    operationdate as date,
    price_per_day as daily_budget,
    spending as actual_spend,
    campaign_id
FROM analytics_reports.spendings_distributed
WHERE
    operationdate >= toDate('{time_from}')
    AND operationdate <= toDate('{time_to}')
    AND country_id = {country}
    AND category_id IN ({categories_str})
    AND category_id IS NOT NULL
    AND ad_id IS NOT NULL
-- ВИДАЛЕНО: AND ad_id GLOBAL IN (SELECT ... FROM enriched_distributed)
ORDER BY ad_id, date, campaign_id DESC
"""
```

**🔗 Пов'язані питання:**
- [Чому кількість оголошень з бюджетом в базі не співпадає з симуляцією?](#чому-кількість-оголошень-з-бюджетом-в-базі-не-співпадає-з-симуляцією)
- [Чому симуляція витягує менше бюджету ніж показує DBeaver?](#чому-симуляція-витягує-менше-бюджету-ніж-показує-dbeaver)

**📖 Джерела:**
- [Task 1.2: Remove impression-presence dependency](../../../openspec/changes/update-paid-eligibility-and-organic-fallback-allocation/tasks.md#1-data-extraction)
- [Task 5.3: Period-level paid flags](../../../openspec/changes/update-paid-eligibility-and-organic-fallback-allocation/tasks.md#5-reporting)
- [IMPLEMENTATION-COMPLETE.md](../../../openspec/changes/update-paid-eligibility-and-organic-fallback-allocation/IMPLEMENTATION-COMPLETE.md)

**📅 Додано:** 2026-02-05

---
