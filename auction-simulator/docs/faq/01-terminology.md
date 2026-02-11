# 📖 Термінологія

Базові терміни та концепції аукційного симулятора.

---

## Різниця між Reach, Impressions і Unique Users

**🏷️ Теги:** `terminology`, `metrics`, `reach`, `impressions`, `users`

**❓ Питання:**
Яка різниця між Reach, Impressions і Unique Users? Чому в звітах 233,806 reach, але 583,065 impressions?

**💡 Коротка відповідь:**
- **Unique Users** = 3,458 (загальна кількість унікальних користувачів)
- **Reach** = 233,806 (кількість комбінацій користувач × оголошення × день)
- **Raw Impressions** = 583,065 (всі перегляди включно з повторами)

**📚 Детальна відповідь:**

Це три **різні метрики**, які не можна порівнювати напряму:

### 1. Unique Users (глобальні унікальні користувачі)

**Визначення:** Кількість унікальних користувачів, які бачили будь-які оголошення за весь період.

**SQL запит:**
```sql
SELECT COUNT(DISTINCT user_id)
FROM enriched_distributed
WHERE ...
-- Результат: 3,458
```

**Що це означає:** 3,458 різних людей побачили оголошення.

### 2. Reach (охоплення = користувач × оголошення × день)

**Визначення:** Кількість унікальних комбінацій "користувач побачив оголошення X в день Y".

**SQL запит:**
```sql
SELECT SUM(cnt) FROM (
    SELECT COUNT(DISTINCT user_id) as cnt
    FROM enriched_distributed
    WHERE ...
    GROUP BY ad_id, toDate(timestamp)
)
-- Результат: 233,806
```

**Що це означає:**
- Якщо користувач побачив оголошення №101 в понеділок → +1 reach
- Той самий користувач побачив те саме оголошення №101 у вівторок → +1 reach (новий день!)
- Той самий користувач побачив оголошення №205 в понеділок → +1 reach (нове оголошення!)

**Чому 233,806?**
- 3,458 користувачів × ~68 комбінацій на користувача = 233,806

### 3. Raw Impressions (сирі покази)

**Визначення:** Загальна кількість переглядів, включаючи повтори в межах однієї комбінації користувач × оголошення × день.

**SQL запит:**
```sql
SELECT COUNT(*)
FROM enriched_distributed
WHERE ...
-- Результат: 583,065
```

**Що це означає:**
- Користувач побачив оголошення №101 о 10:00 → +1 impression
- Той самий користувач побачив те саме оголошення №101 о 14:00 (той самий день!) → +1 impression
- Але це все ще **1 reach** (та сама комбінація користувач × оголошення × день)

**Чому 583,065?**
- 233,806 reach × ~2.49 переглядів на комбінацію = 583,065

### Співвідношення метрик:

```
583,065 impressions
   ↓ (згрупувати за user × ad × day)
233,806 reach records
   ↓ (згрупувати за user globally)
3,458 unique users

Співвідношення:
- Impressions per reach: 2.49× (кожна комбінація переглядалась 2.5 рази в середньому)
- Reach per unique user: ~68 (кожен користувач бачив 68 різних комбінацій ad×day)
```

### Що використовує симулятор?

**Симулятор працює з REACH, а не з raw impressions:**

- Вхідні дані: 233,806 reach records (користувач × оголошення × день)
- Симуляція: Розподіляє ці 233,806 reach між платними та органічними
- Вихідні дані: Порівнює фактичний та симульований reach

**Чому не impressions?**
- Raw impressions включають повтори в межах дня (користувач скролить ленту кілька разів)
- Аукціон платить за **досягнення користувача**, а не за кожен перегляд
- 1 користувач × 1 оголошення × 1 день = 1 платна одиниця (reach)

### Приклад з реальних даних:

**Категорія 1361, період 2026-01-31 до 2026-02-01:**

| Метрика | Значення | Перевірка |
|---------|----------|-----------|
| Unique Users | 3,458 | `COUNT(DISTINCT user_id)` |
| Total Reach | 233,806 | `SUM(COUNT(DISTINCT user_id) GROUP BY ad, date)` |
| Raw Impressions | 583,065 | `COUNT(*)` |
| Impressions/Reach | 2.49× | 583,065 / 233,806 |
| Reach/User | ~68 | 233,806 / 3,458 |

**💻 Де побачити у звітах:**

У `summary_statistics_*.txt`:

```
Unique Users (globally):
  Estimated: ~3,458

Total Reach (user × ad × date combinations):
  Actual:    233,806
  Simulated: 233,806

Raw Impressions (all views):
  Actual:    583,065
  Note: Simulation operates on reach, not raw impressions
```

**🔗 Пов'язані питання:**
- [Чому бюджет 240 AZN, але симуляція показує 139 AZN?](./07-data-extraction.md)
- [Як перевірити точність симуляції?](./06-troubleshooting.md)

**📖 Джерела:**
- OpenSpec: [fix-reach-impressions-terminology](../../openspec/changes/fix-reach-impressions-terminology/)
- Код: [reporting.py:310-366](../../src/auction_simulator/reporting.py)

**📅 Додано:** 2026-02-02
**📅 Оновлено:** 2026-02-02

---

## Що таке N?

**🏷️ Теги:** `terminology`, `auction`, `N`, `ads_with_budget`

**❓ Питання:**
Що таке N і чому він дорівнює 81?

**💡 Коротка відповідь:**
**N** = кількість оголошень з `remaining_budget > 0` (які можуть платити в даний момент)

**📚 Детальна відповідь:**

N (ads_with_budget) — це кількість оголошень, які можуть платити в поточний момент аукціону. Це **не** загальна кількість оголошень, а лише ті що мають бюджет.

**Чому 81?**

У категорії 1361 на 2026-01-22:
- **Всього оголошень:** 5,171
- **З бюджетом > 0:** 81
- **Без бюджету (organic):** 5,090

Тому N = 81.

**N змінюється динамічно:**

| Час | N | Пояснення |
|-----|---|-----------|
| 00:00 | 81 | Початок дня, всі з бюджетом |
| 12:00 | 75 | 6 оголошень вичерпали бюджет |
| 18:00 | 50 | Ще 25 вичерпали бюджет |
| 23:00 | 10 | Більшість вичерпала бюджет |

**💻 Код:**

```python
# Локація: auction_engine.py:155
ads_with_budget = [ad for ad in eligible if ad.remaining_budget > 0]
N = len(ads_with_budget)

# N використовується у формулі effective_bid
effective_bid = min_bid + (N - 1 - rank_index) * bid_step
```

**🔗 Пов'язані питання:**
- [Як розраховується effective_bid?](./02-auction-mechanics.md#як-розраховується-effective_bid)
- [N=300 чи N=40 коли 300 ads, 40 slots?](./02-auction-mechanics.md#n300-чи-n40)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:96](../../openspec/specs/auction-engine/spec.md#L96)
- Код: [auction_engine.py](../../src/auction_simulator/auction_engine.py)

**📅 Додано:** 2026-01-30

---

## Різниця між effective_bid і min_bid

**🏷️ Теги:** `terminology`, `bidding`, `pricing`

**❓ Питання:**
Яка різниця між effective_bid і min_bid? Чому effective_bid майже вдвічі більший?

**💡 Коротка відповідь:**

- **min_bid** = базова ціна за показ (з PostgreSQL)
- **effective_bid** = фактична ставка з урахуванням конкуренції

**📚 Детальна відповідь:**

### min_bid (мінімальна ціна)

- **Джерело:** PostgreSQL таблиця `campaign_ad_price`
- **Формула:** `price_per_day / fact_impression`
- **Приклад:** 0.0702 копійок для категорії 1361
- **Призначення:** Базова ціна, нижче якої ніхто не може платити

### effective_bid (ефективна ставка)

- **Формула:** `min_bid + (N - 1 - rank_index) × bid_step`
- **Приклад (N=81, rank=0):** `0.0702 + 80×0.001 = 0.1502` коп.
- **Призначення:** Фактична ставка з урахуванням позиції в рейтингу

### Чому різниця?

Оголошення з вищою **pressure** (срочністю витратити бюджет) отримують бонус до ставки:

| Ранг | Pressure | Effective Bid | Множник від min_bid |
|------|----------|---------------|---------------------|
| 0 (найвища) | 150.0 | 0.1502 коп. | 2.14× |
| 40 (середина) | 80.0 | 0.1102 коп. | 1.57× |
| 80 (найнижча) | 10.5 | 0.0702 коп. | 1.00× (= min_bid) |

**Висновок:** Чим вища срочність витратити бюджет, тим вища ставка, тим більша ймовірність виграти.

**💻 Код:**

```python
# Локація: auction_engine.py:180-185
def calculate_effective_bid(self, rank_index: int, ads_with_budget_count: int) -> float:
    N = max(ads_with_budget_count, 1)
    bonus = (N - 1 - rank_index) * self.bid_step
    effective_bid = self.min_bid + bonus
    return effective_bid
```

**🔗 Пов'язані питання:**
- [Що таке pressure?](#що-таке-pressure)
- [Як розраховується effective_bid?](./02-auction-mechanics.md#як-розраховується-effective_bid)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:87-99](../../openspec/specs/auction-engine/spec.md#L87-L99)

**📅 Додано:** 2026-01-30

---

## Що таке pressure?

**🏷️ Теги:** `terminology`, `ranking`, `urgency`

**❓ Питання:**
Що таке pressure і як він розраховується?

**💡 Коротка відповідь:**
**Pressure** = срочність витратити бюджет = `remaining_budget / time_left`

**📚 Детальна відповідь:**

Pressure визначає **наскільки срочно** оголошенню потрібно витрачати бюджет.

### Формула:

```python
pressure = remaining_budget / max(time_left, min_time_left_threshold)
```

Де:
- `remaining_budget` = залишковий бюджет (копійки)
- `time_left` = частка дня що залишилась (0.0-1.0)
- `min_time_left_threshold` = 0.001 (захист від ділення на нуль)

### Приклади:

**Рівномірна витрата (ідеальна):**

| Час | Бюджет | time_left | Pressure | Статус |
|-----|--------|-----------|----------|--------|
| 00:00 | 100 коп. | 1.0 | 100 | ✅ Нормально |
| 06:00 | 75 коп. | 0.75 | 100 | ✅ Нормально |
| 12:00 | 50 коп. | 0.5 | 100 | ✅ Нормально |
| 18:00 | 25 коп. | 0.25 | 100 | ✅ Нормально |

**Повільна витрата (підвищена pressure):**

| Час | Бюджет | time_left | Pressure | Статус |
|-----|--------|-----------|----------|--------|
| 12:00 | 80 коп. | 0.5 | 160 | ⚠️ Треба швидше! |
| 18:00 | 60 коп. | 0.25 | 240 | 🔥 Дуже срочно! |

**Швидка витрата (знижена pressure):**

| Час | Бюджет | time_left | Pressure | Статус |
|-----|--------|-----------|----------|--------|
| 06:00 | 10 коп. | 0.75 | 13.3 | 📉 Майже витрачено |

### Як використовується?

1. **Розрахунок pressure** для кожного оголошення
2. **Сортування** за pressure (від найвищої до найнижчої)
3. **Присвоєння rank_index**: 0 = найвища pressure
4. **Розрахунок effective_bid** на основі rank

**💻 Код:**

```python
# Локація: auction_engine.py:49-67
def calculate_pressure(self, ad: Ad, time_left: float) -> float:
    if ad.remaining_budget <= 0:
        return 0.0

    safe_time_left = max(time_left, self.min_time_left_threshold)
    pressure = ad.remaining_budget / safe_time_left

    return pressure
```

**🔗 Пов'язані питання:**
- [Що таке time_left?](./03-pacing-gate.md#time_progress-і-time_left)
- [Що таке rank_index?](#що-таке-rank_index)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:6-34](../../openspec/specs/auction-engine/spec.md#L6-L34)

**📅 Додано:** 2026-01-30

---

## Що таке rank_index?

**🏷️ Теги:** `terminology`, `ranking`, `position`

**❓ Питання:**
Що таке rank_index і як він використовується?

**💡 Коротка відповідь:**
**rank_index** = позиція в рейтингу за pressure (0 = найкраща позиція)

**📚 Детальна відповідь:**

Після розрахунку pressure для всіх оголошень, система сортує їх і присвоює кожному порядковий номер (rank_index).

### Як присвоюється:

```python
# 1. Сортування за pressure (спадання)
ads_sorted = sorted(ads, key=lambda ad: ad.pressure, reverse=True)

# 2. Присвоєння rank_index
for rank_index, ad in enumerate(ads_sorted):
    ad.rank_index = rank_index  # 0, 1, 2, ..., N-1
```

### Приклад:

| Ad ID | Pressure | rank_index | Ставка |
|-------|----------|------------|--------|
| 101 | 500.0 | **0** | min_bid + 80×step (найвища) |
| 205 | 350.0 | 1 | min_bid + 79×step |
| 342 | 280.0 | 2 | min_bid + 78×step |
| ... | ... | ... | ... |
| 789 | 10.5 | **80** | min_bid + 0×step (найнижча) |

### Використання у формулі:

```python
effective_bid = min_bid + (N - 1 - rank_index) × bid_step
```

**Чому (N - 1 - rank_index)?**
- Інвертує позицію: найвища pressure → найвища ставка
- rank=0 → бонус = (81-1-0) = 80 кроків
- rank=80 → бонус = (81-1-80) = 0 кроків

**🔗 Пов'язані питання:**
- [Чому формула (N-1-rank)?](./02-auction-mechanics.md#чому-формула-n-1-rank)
- [Як розраховується effective_bid?](./02-auction-mechanics.md#як-розраховується-effective_bid)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:76-85](../../openspec/specs/auction-engine/spec.md#L76-L85)

**📅 Додано:** 2026-01-30

---

## Всі терміни (швидкий довідник)

### Метрики даних

| Термін | Значення | SQL запит |
|--------|----------|-----------|
| **Unique Users** | Унікальні користувачі (глобально) | `COUNT(DISTINCT user_id)` |
| **Reach** | Користувач × оголошення × день | `SUM(COUNT(DISTINCT user_id) GROUP BY ad, date)` |
| **Raw Impressions** | Всі перегляди з повторами | `COUNT(*)` |
| **Organic Reach** | Reach без плати | `WHERE campaign_show_ad != 'True'` |
| **Paid Reach** | Reach з платою | `WHERE campaign_show_ad = 'True'` |

### Параметри аукціону

| Термін | Значення | Одиниці |
|--------|----------|---------|
| **N** | Кількість ads з budget > 0 | int |
| **pressure** | remaining_budget / time_left | float |
| **rank_index** | Позиція в рейтингу (0 = best) | int (0 до N-1) |
| **min_bid** | Мінімальна ціна показу | копійки |
| **bid_step** | Крок збільшення ставки | копійки (0.001) |
| **effective_bid** | Фактична ставка | копійки |
| **time_left** | Частка дня що залишилась | float (0.0-1.0) |
| **time_progress** | Частка дня що минула | float (0.0-1.0) |
| **batch_size** | Слотів у батчі | int (40) |
| **kopecks** | 1/100 AZN | float |

---

[⬅️ Назад до індексу](./README.md)
