# Аналіз та план покращень: Organic Fallback та Budget Utilization

**Дата:** 2026-02-05
**Статус:** Аналіз та тестування

---

## 🎯 Поточний стан (Baseline)

### Симуляція: 2026-01-31 до 2026-02-01, категорія 1361

| Метрика | Значення | Оцінка |
|---------|----------|--------|
| **Budget Utilization** | 94.0% (216.38/230.25 AZN) | ⚠️ Можна краще |
| **Paid ads reach coverage** | 141/141 (100%) | ✅ Відмінно |
| **Free ads reach coverage** | 5/8,266 (0.06%) | ❌ **КРИТИЧНО** |
| **Organic to paid exhausted** | ~97% | ❌ **КРИТИЧНО** |
| **Organic to free ads** | ~3% | ❌ **КРИТИЧНО** |

---

## 📋 Виявлені проблеми

### Проблема #1: 10 оголошень з category_id=0.0 (13.25 AZN втрачено)

**Причина:**
- Budget extraction фільтрує через subquery з `enriched_distributed WHERE category_id IN (...)`
- Але якщо в `enriched_distributed` для деяких ad_id є записи з category_id=NULL/0, вони проходять фільтр
- Budget для цих оголошень завантажується, але reach=0 (не в категорії 1361)

**Приклад:**
```
ad_id=56266093: budget=0.6 AZN, category_id=0.0, reach=0
ad_id=70319254: budget=1.65 AZN, category_id=0.0, reach=0
```

### Проблема #2: 99.94% безкоштовних оголошень отримують 0 reach

**Причина:**
Алгоритм `distribute_organic_proportional` використовує:
```python
proportion = ad.total_reach_historical / total_reach_sum
allocation = floor(remaining_slots × proportion)
```

**Наслідок:**
- Платні оголошення: historical reach = 600-1,073 → allocation = 1-3 slots
- Безкоштовні: historical reach = 21.76 (середнє) → allocation = floor(0.0038) = 0

**Математика:**
```
Типове безкоштовне оголошення:
- historical_reach = 22
- total_sum = 233,806
- proportion = 22 / 233,806 = 0.000094
- remaining_slots = 40
- allocation = floor(40 × 0.000094) = floor(0.0038) = 0 ❌
```

### Проблема #3: Budget utilization 94% (залишок 13.87 AZN)

**Причини:**
1. **13.25 AZN**: 10 оголошень з category_id=0 не брали участь
2. **0.67 AZN**: 4 оголошення дійшли до кінця дня з залишком бюджету

**Приклад кінця дня (час 23:00):**
```json
{
  "hour": 23,
  "total_reach": 22,  // тільки 22 слоти
  "ads_with_budget": 4,
  "remaining_budgets": [25.69, 19.58, 13.16, 7.73] // копійки
}
```

---

## 🔧 ЗАПРОПОНОВАНІ РІШЕННЯ

### Рішення #1: Фільтрація категорії при екстракції даних

#### Варіант 1A: Строга фільтрація (рекомендовано)

**Зміна:** `data_extraction.py:341`
```python
# Додати фільтр category_id в subquery
AND category_id IN ({categories_str})
AND category_id IS NOT NULL  # додати
```

**Плюси:**
- ✅ Чисті дані: тільки оголошення з правильною категорією
- ✅ Немає "втрачених" бюджетів
- ✅ Прозорість: що бачимо, те симулюємо

**Мінуси:**
- ⚠️ Втрачаємо 10 оголошень з бюджетом, які могли мати reach в реальності

#### Варіант 1B: Включити оголошення з бюджетом незалежно від reach

**Зміна:** `simulation.py:95-99`
```python
# При reset_daily_budgets додавати оголошення з бюджетом навіть якщо немає reach
for _, row in daily_budgets.iterrows():
    ad_id = row['ad_id']
    if ad_id not in self.ads:
        # Створити Ad об'єкт з category_id з budgets або default
        seller_id = row.get('seller_id', 0)
        category_id = row.get('category_id', categories[0])  # використати першу категорію
        self.ads[ad_id] = Ad(
            ad_id=ad_id,
            seller_id=seller_id,
            category_id=category_id,
            daily_budget=0.0,
            remaining_budget=0.0,
            actual_spend=0.0,
            simulated_reach=0,
            simulated_spending=0.0,
            total_reach_historical=0,  # немає історичного reach
            raw_impressions_historical=0
        )
    budget = float(row['daily_budget'])
    self.ads[ad_id].daily_budget = budget
    self.ads[ad_id].remaining_budget = budget
```

**Плюси:**
- ✅ Всі оголошення з бюджетом беруть участь в аукціоні
- ✅ 100% budget utilization (якщо є reach)

**Мінуси:**
- ⚠️ Оголошення без історичного reach отримають 0 через organic fallback
- ⚠️ Складніша логіка

**Рекомендація:** Варіант 1A (строга фільтрація)

---

### Рішення #2: Покращений organic fallback розподіл

#### Варіант 2A: Розділення paid_exhausted та free ads (рекомендовано)

**Зміна:** `auction_engine.py:373-486`
```python
def distribute_organic_proportional(
    self,
    ads: List[Ad],
    remaining_slots: int,
    category_id: int = None,
    hour: int = None,
    sim_logger=None
):
    """
    Розподіл органічного reach:
    - 20% для платних оголошень з витраченим бюджетом (пропорційно)
    - 80% для безкоштовних оголошень (рівномірно або пропорційно)
    """
    if remaining_slots <= 0:
        return

    # Розділити на paid_exhausted та free
    paid_exhausted = [ad for ad in ads if ad.daily_budget > 0 and ad.remaining_budget == 0]
    free_ads = [ad for ad in ads if ad.daily_budget == 0]

    # Розрахувати розподіл
    paid_slots = int(remaining_slots * 0.2)  # 20% для paid exhausted
    free_slots = remaining_slots - paid_slots  # 80% для free

    # Розподіл для paid_exhausted (пропорційно total_reach_historical)
    if paid_slots > 0 and len(paid_exhausted) > 0:
        self._allocate_proportional(paid_exhausted, paid_slots)

    # Розподіл для free_ads (рівномірно з мінімальною гарантією)
    if free_slots > 0 and len(free_ads) > 0:
        self._allocate_with_minimum(free_ads, free_slots, minimum=1)
```

**Додаткові методи:**
```python
def _allocate_with_minimum(self, ads: List[Ad], slots: int, minimum: int = 1):
    """
    Розподіл з мінімальною гарантією 1 slot на оголошення.

    Алгоритм:
    1. Спочатку дати по minimum кожному (якщо достатньо)
    2. Залишок розподілити пропорційно
    """
    if slots < len(ads) * minimum:
        # Недостатньо для гарантії - розподілити пропорційно
        self._allocate_proportional(ads, slots)
        return

    # Дати по minimum кожному
    for ad in ads:
        ad.simulated_reach += minimum

    # Залишок розподілити пропорційно
    remainder = slots - len(ads) * minimum
    if remainder > 0:
        self._allocate_proportional(ads, remainder)
```

**Плюси:**
- ✅ Всі безкоштовні оголошення отримують хоча б 1 reach (якщо достатньо слотів)
- ✅ Платні exhausted все ще отримують бонус за попередню активність
- ✅ Баланс між "fairness" та "popularity-based"

**Мінуси:**
- ⚠️ Потрібно налаштувати співвідношення (20/80 може не бути оптимальним)
- ⚠️ Більш складна логіка

#### Варіант 2B: Scaling up для малих пропорцій

**Зміна:** `auction_engine.py:420-433`
```python
# Замість floor() використати ceiling() для малих пропорцій
for ad, proportion in proportions:
    if proportion * remaining_slots < 1.0:
        # Малі пропорції - використати scaling
        scaled_proportion = min(1.0 / len(ads), proportion * 10)
        base = math.floor(remaining_slots * scaled_proportion)
    else:
        base = math.floor(remaining_slots * proportion)
    allocations[ad.ad_id] = base
    total_allocated += base
```

**Плюси:**
- ✅ Простіше в реалізації
- ✅ Зберігає пропорційність

**Мінуси:**
- ⚠️ Може порушити conservation (потрібно нормалізувати)
- ⚠️ Все ще не гарантує reach для всіх

**Рекомендація:** Варіант 2A (розділення paid/free з мінімумом)

---

### Рішення #3: Покращення budget utilization

#### Варіант 3A: Збільшення bid_step (простий)

**Зміна:** `config/local.yaml:20`
```yaml
bid_step: 0.005  # було 0.003
```

**Очікувані наслідки:**
- Більші біди → швидше витрачання бюджету
- Менш точна симуляція (відхилення від історичних даних)

**Плюси:**
- ✅ Дуже просто
- ✅ Швидше витрачання в останні години

**Мінуси:**
- ⚠️ Може зіпсувати точність симуляції (93% → ?)
- ⚠️ Потрібно перетестувати та знайти новий оптимум

#### Варіант 3B: Dynamic pressure multiplier в останні години

**Зміна:** `auction_engine.py:50-70`
```python
def calculate_pressure(self, ad: Ad, time_left: float) -> float:
    """
    Розрахунок pressure з dynamic multiplier в останні години.
    """
    if time_left < self.min_time_left_threshold:
        time_left = self.min_time_left_threshold

    base_pressure = ad.remaining_budget / time_left

    # Dynamic multiplier для останніх годин
    if time_left < 0.1:  # останні 2.4 години
        multiplier = 2.0  # подвоїти urgency
    elif time_left < 0.2:  # останні 4.8 години
        multiplier = 1.5
    else:
        multiplier = 1.0

    return base_pressure * multiplier
```

**Плюси:**
- ✅ Збільшує агресивність наприкінці дня
- ✅ Не змінює раннє витрачання (pacing gate залишається)

**Мінуси:**
- ⚠️ Може порушити pacing gate в останні години
- ⚠️ Потрібно налаштовувати threshold та multiplier

#### Варіант 3C: Адаптивний bid_step

**Зміна:** `auction_engine.py:178-220`
```python
def select_winners(
    self,
    ranked_ads: List[Tuple[Ad, float, int]],
    min_bid: float,
    batch_size: int,
    time_left: float = None,  # додати
    logger=None,
    batch_number: int = None,
    category_id: int = None,
    hour: int = None
) -> List[Tuple[Ad, float, int]]:
    """
    Select winners with adaptive bid_step.
    """
    # Адаптивний bid_step
    if time_left and time_left < 0.1:
        bid_step = self.bid_step * 2.0  # подвоїти в останні години
    else:
        bid_step = self.bid_step

    N = len(ranked_ads)
    winners = []

    for ad, pressure, rank_index in ranked_ads:
        if len(winners) >= batch_size:
            break

        effective_bid = min_bid + (N - 1 - rank_index) * bid_step

        if ad.remaining_budget >= effective_bid:
            winners.append((ad, effective_bid, rank_index))
            ad.remaining_budget -= effective_bid
            ad.simulated_spending += effective_bid
            ad.simulated_reach += 1

    return winners
```

**Плюси:**
- ✅ Гнучкий підхід
- ✅ Не впливає на ранні години

**Мінуси:**
- ⚠️ Потрібно передавати time_left через всі виклики
- ⚠️ Складніше тестувати

**Рекомендація:** Почати з Варіант 3A (збільшення bid_step до 0.005), якщо недостатньо - додати 3B

---

## 🧪 ПЛАН ТЕСТУВАННЯ

### Фаза 1: Baseline повторення (контроль)

```bash
python -m auction_simulator.cli simulate \
  --country 13 \
  --categories 1361 \
  --time-from 2026-01-31 \
  --time-to 2026-02-01 \
  --config config/local.yaml \
  --no-cache
```

**Очікувані результати:**
- Budget utilization: 94%
- Free ads coverage: 0.06%
- Paid ads coverage: 100%

### Фаза 2: Тест #1 - Строга фільтрація (Рішення 1A)

**Зміни:**
- `data_extraction.py:341`: додати `AND category_id IS NOT NULL`

**Очікувані результати:**
- Budget utilization: ~100% (без category_id=0 оголошень)
- Total budget: 217 AZN (замість 230.25 AZN)
- Free ads coverage: без змін (0.06%)

### Фаза 3: Тест #2 - Покращений organic fallback (Рішення 2A)

**Зміни:**
- `auction_engine.py:373-486`: розділення paid/free 20/80 з мінімумом 1

**Очікувані результати:**
- Free ads coverage: 80-100% (залежно від кількості слотів)
- Organic distribution: ~20% paid_exhausted, ~80% free

**Метрики для аналізу:**
```python
# Після симуляції
free_ads_with_reach = sum(1 for ad in ads if ad.daily_budget == 0 and ad.simulated_reach > 0)
free_ads_total = sum(1 for ad in ads if ad.daily_budget == 0)
coverage = free_ads_with_reach / free_ads_total * 100

paid_exhausted_reach = sum(ad.simulated_reach for ad in ads if ad.daily_budget > 0 and ad.remaining_budget == 0)
free_reach = sum(ad.simulated_reach for ad in ads if ad.daily_budget == 0)
```

### Фаза 4: Тест #3 - Збільшення bid_step (Рішення 3A)

**Варіанти для тестування:**
- bid_step = 0.003 (baseline)
- bid_step = 0.004 (+33%)
- bid_step = 0.005 (+67%)
- bid_step = 0.006 (+100%)

**Метрики:**
```python
# Reach accuracy (з FAQ #2)
reach_accuracy = (1 - abs(simulated_paid - actual_paid) / actual_paid) * 100

# Budget utilization
budget_utilization = simulated_spending / total_budget * 100

# Paid/Organic split
paid_percentage = paid_reach / total_reach * 100
organic_percentage = organic_reach / total_reach * 100
```

**Очікування:**
| bid_step | Reach Accuracy | Budget Util | Paid/Organic |
|----------|---------------|-------------|--------------|
| 0.003 | 93% | 94% | 97%/3% |
| 0.004 | ? | 97% | ?/?  |
| 0.005 | ? | 99% | ?/? |
| 0.006 | ? | 100% | ?/? |

### Фаза 5: Тест #4 - Dynamic pressure (Рішення 3B)

**Зміни:**
- `auction_engine.py:50-70`: додати multiplier для time_left < 0.1

**Варіанти:**
- Multiplier = 1.5 (помірний)
- Multiplier = 2.0 (агресивний)
- Multiplier = 3.0 (дуже агресивний)

### Фаза 6: Комбінований тест (найкращі рішення)

**Комбінація:**
- Рішення 1A (строга фільтрація)
- Рішення 2A (покращений organic 20/80 з мінімумом)
- Рішення 3A (bid_step = 0.005) АБО 3B (dynamic pressure)

**Очікувані результати:**
- Budget utilization: 99-100%
- Free ads coverage: 80-100%
- Paid ads coverage: 100%
- Reach accuracy: 85-93%

---

## 📊 МЕТРИКИ ОЦІНКИ

### Критичні метрики (мають покращитись)

1. **Free ads coverage:** 0.06% → **≥80%**
2. **Budget utilization:** 94% → **≥98%**
3. **Organic to free ads:** 3% → **≥60%**

### Додаткові метрики (не повинні погіршитись)

4. **Reach accuracy:** 93% → **≥85%** (допускається невелике погіршення)
5. **Paid ads coverage:** 100% → **100%** (не змінювати)
6. **Total reach conservation:** 100% → **100%** (строга вимога)

---

## ✅ РЕКОМЕНДОВАНИЙ ПЛАН ВПРОВАДЖЕННЯ

### Крок 1: Швидкі покращення (1-2 години)

**Зміни:**
1. Рішення 1A: Строга фільтрація category_id
2. Рішення 3A: Збільшення bid_step до 0.005

**Очікуване покращення:**
- Budget utilization: 94% → 98%
- Без зміни organic distribution

### Крок 2: Основне покращення (4-6 годин)

**Зміна:**
3. Рішення 2A: Покращений organic fallback (20/80 з мінімумом)

**Очікуване покращення:**
- Free ads coverage: 0.06% → 80-100%
- Organic to free ads: 3% → 60-80%

### Крок 3: Фінальне тюнінгування (2-3 години)

**Дії:**
- Тестування різних bid_step (0.004, 0.005, 0.006)
- Тестування співвідношення paid/free (15/85, 20/80, 25/75)
- Тестування мінімуму (1, 2, 3)

**Обрати оптимальні параметри за метриками.**

### Крок 4: Валідація (1-2 години)

**Тести:**
- Різні категорії
- Різні періоди (1 день, 3 дні, тиждень)
- Різні сценарії (багато/мало бюджету)

---

## 🎯 ЦІЛЬОВІ ПОКАЗНИКИ (після всіх змін)

| Метрика | Поточна | Ціль | Критичність |
|---------|---------|------|-------------|
| Budget utilization | 94.0% | ≥98% | 🔴 Висока |
| Free ads coverage | 0.06% | ≥80% | 🔴 **КРИТИЧНА** |
| Organic to free | 3% | ≥60% | 🔴 **КРИТИЧНА** |
| Paid ads coverage | 100% | 100% | 🔴 Висока |
| Reach accuracy | 93% | ≥85% | 🟡 Середня |

