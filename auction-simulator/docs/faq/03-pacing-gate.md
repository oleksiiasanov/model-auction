# 🚦 Pacing Gate

Механізм контролю темпу витрат бюджету протягом дня.

---

## time_progress і time_left

**🏷️ Теги:** `pacing`, `time`, `progress`

**❓ Питання:**
Що таке time_progress і time_left? Як вони розраховуються?

**💡 Коротка відповідь:**
- **time_progress** = частка дня що **минула** (0.0 до 1.0)
- **time_left** = частка дня що **залишилась** (1.0 до 0.0)

**📚 Детальна відповідь:**

### Формули:

```python
time_progress = hour / 24.0
time_left = (24 - hour) / 24.0
```

### Важливо:
- Оновлюються **РАЗ НА ГОДИНУ** (не в кожному батчі!)
- hour ∈ [0, 23] (ніколи не буває 24)
- time_progress + time_left = 1.0 (завжди)

### Приклади:

| Час | hour | time_progress | time_left | Пояснення |
|-----|------|---------------|-----------|-----------|
| 00:00 | 0 | 0.0 | 1.0 | Початок дня |
| 01:00 | 1 | 0.042 | 0.958 | 4.2% минуло |
| 06:00 | 6 | 0.25 | 0.75 | Чверть дня |
| 12:00 | 12 | 0.5 | 0.5 | Половина дня |
| 18:00 | 18 | 0.75 | 0.25 | 75% минуло |
| 23:00 | 23 | 0.958 | 0.042 | Кінець дня |
| 23:59 | 23 | 0.958 | 0.042 | Ще та ж година! |

### Де використовуються:

**time_left → pressure:**
```python
pressure = remaining_budget / max(time_left, min_time_left_threshold)
```

**time_progress → pacing gate:**
```python
expected_spend = daily_budget × time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

**💻 Код:**

```python
# Локація: simulation.py:239-240
time_progress = hour / 24.0
time_left = (24 - hour) / 24.0
```

**🔗 Пов'язані питання:**
- [Що таке pressure?](./01-terminology.md#що-таке-pressure)
- [Що таке pacing_tolerance?](#pacing_tolerance)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:36-50](../../openspec/specs/auction-engine/spec.md#L36-L50)

**📅 Додано:** 2026-01-30

---

## pacing_tolerance

**🏷️ Теги:** `pacing`, `budget`, `tolerance`

**❓ Питання:**
Що таке pacing_tolerance і навіщо він потрібен?

**💡 Коротка відповідь:**
**pacing_tolerance** = допустимий відсоток перевищення очікуваних витрат (зазвичай 0.2 = 20%)

**📚 Детальна відповідь:**

### Призначення:

Дозволяє оголошенням витрачати **трохи більше** ніж ідеальний темп, щоб уникнути блокування через мінімальні відхилення.

### Формула:

```python
expected_spend = daily_budget × time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)

# Перевірка:
if actual_spend > max_allowed:
    # Заблоковано! Pressure = 0
else:
    # Дозволено участвувати
```

### Приклад (daily_budget=100 коп., pacing_tolerance=0.2):

| Час | time_progress | expected | max_allowed (20%) | actual_spend | Статус |
|-----|---------------|----------|-------------------|--------------|--------|
| 00:00 | 0.0 | 0 коп. | **0 коп.** | 0 коп. | ✅ OK |
| 00:00 | 0.0 | 0 коп. | **0 коп.** | 0.15 коп. | ❌ **BLOCKED** |
| 06:00 | 0.25 | 25 коп. | **30 коп.** | 28 коп. | ✅ OK |
| 06:00 | 0.25 | 25 коп. | **30 коп.** | 31 коп. | ❌ BLOCKED |
| 12:00 | 0.5 | 50 коп. | **60 коп.** | 55 коп. | ✅ OK |
| 18:00 | 0.75 | 75 коп. | **90 коп.** | 85 коп. | ✅ OK |

### Навіщо tolerance?

**БЕЗ tolerance (tolerance=0):**
```
Точно 12:00, очікується 50.0 коп.
Оголошення витратило 50.1 коп.
50.1 > 50.0 → ЗАБЛОКОВАНО через 0.1 копійки! ❌
```

**З tolerance=0.2:**
```
Точно 12:00, max_allowed = 50 × 1.2 = 60 коп.
Оголошення витратило 50.1 коп.
50.1 < 60.0 → ✅ ДОЗВОЛЕНО
```

### Баланс:

| tolerance | Поведінка | Проблеми |
|-----------|-----------|----------|
| 0.0 | Дуже строго | Постійні блокування через копійки |
| 0.2 | Оптимально | Дозволяє 20% відхилення |
| 1.0 | Дуже вільно | Можна витратити 100% за півдня |

**💻 Код:**

```python
# Локація: auction_engine.py:83-86
expected_spend = ad.daily_budget * time_progress
max_allowed = expected_spend * (1 + self.pacing_tolerance)

is_eligible = ad.actual_spend <= max_allowed
```

**🔗 Пов'язані питання:**
- [Чому pacing gate блокує все о 00:00?](#проблема-hour0)
- [Що таке time_progress?](#time_progress-і-time_left)

**📖 Джерела:**
- Config: [local.yaml:10](../../config/local.yaml#L10)
- Spec: [auction-engine/spec.md:36-50](../../openspec/specs/auction-engine/spec.md#L36-L50)

**📅 Додано:** 2026-01-30

---

## min_time_left_threshold

**🏷️ Теги:** `pacing`, `epsilon`, `safety`, `edge-case`

**❓ Питання:**
Навіщо потрібен min_time_left_threshold (колишній epsilon)? Коли він спрацьовує?

**💡 Коротка відповідь:**
**min_time_left_threshold** = мінімальне значення для time_left (0.001) — захист на випадок майбутніх змін.

**📚 Детальна відповідь:**

### Формула:

```python
safe_time_left = max(time_left, min_time_left_threshold)
pressure = remaining_budget / safe_time_left
```

### Чи спрацьовує зараз?

**НІ!** При поточній реалізації (hourly updates):

| Час | hour | time_left | min_threshold | Спрацьовує? |
|-----|------|-----------|---------------|-------------|
| 00:00 | 0 | 1.000 | 0.001 | ❌ НІ |
| 12:00 | 12 | 0.500 | 0.001 | ❌ НІ |
| 23:00 | 23 | **0.042** | 0.001 | ❌ НІ |

**Мінімальне реальне time_left = 0.042 (година 23)**
**0.042 > 0.001** → threshold ніколи не використовується!

### Навіщо тоді він потрібен?

**Defensive programming** — захист на випадок:

1. **Майбутніх змін:**
   ```python
   # Якщо перейдуть на поминутне оновлення:
   time_left = (1440 - minute) / 1440.0
   # О 23:59 → time_left = 1/1440 = 0.0007 < 0.001
   # Тоді threshold спрацює!
   ```

2. **Крайніх випадків:**
   ```python
   # Теоретично якщо hour=24 (хоч це неможливо):
   time_left = (24 - 24) / 24.0 = 0.0
   safe_time_left = max(0.0, 0.001) = 0.001 ✅
   ```

3. **Помилок округлення:**
   Захист від незвичайних float помилок (малоймовірно але можливо)

### Коли б спрацював?

```python
# Приклад: посекундне оновлення
second = 86399  # 23:59:59
time_left = (86400 - 86399) / 86400.0 = 0.000012

safe_time_left = max(0.000012, 0.001) = 0.001  # Threshold застосовується!
pressure = 10 / 0.001 = 10,000  # Обмежена pressure
```

**БЕЗ threshold:**
```python
pressure = 10 / 0.000012 = 833,333  # Надто велика!
```

### Висновок:

✅ **Зараз не використовується** (min real time_left = 0.042)
✅ **Корисний для майбутнього** (minute/second updates)
✅ **Захищає від edge cases** (div by zero, float errors)

**💻 Код:**

```python
# Локація: auction_engine.py:63-65
safe_time_left = max(time_left, self.min_time_left_threshold)
pressure = ad.remaining_budget / safe_time_left
```

**🔗 Пов'язані питання:**
- [Що таке time_left?](#time_progress-і-time_left)
- [Що таке pressure?](./01-terminology.md#що-таке-pressure)

**📖 Джерела:**
- Config: [local.yaml:5-8](../../config/local.yaml#L5-L8)
- Spec: [auction-engine/spec.md:26-34](../../openspec/specs/auction-engine/spec.md#L26-L34)

**📅 Додано:** 2026-01-30

---

## Проблема hour=0

**🏷️ Теги:** `pacing`, `bug`, `blocking`, `hour-zero`

**❓ Питання:**
Чому pacing gate блокує всі оголошення о 00:00 після першого батчу?

**💡 Коротка відповідь:**
Тому що `time_progress = 0 / 24.0 = 0` → `max_allowed = 0 × 1.2 = 0` → будь-які витрати блокуються!

**📚 Детальна відповідь:**

### Проблема:

**О 00:00 (перша година дня):**

```python
hour = 0
time_progress = 0 / 24.0 = 0.0

expected_spend = 100 × 0.0 = 0 коп.
max_allowed = 0 × 1.2 = 0 коп.

# Після першого батчу:
actual_spend = 0.15 коп.  # Виграли і заплатили
0.15 > 0 → ❌ ЗАБЛОКОВАНО!

# ВСІ оголошення блокуються після першого батчу!
```

### Візуалізація проблеми:

```
Батч #1 (00:00):
  ├─ max_allowed = 0
  ├─ Ad A (budget=100): actual_spend=0 → 0 <= 0 ✅ Участвує
  ├─ Ad A виграє, платить 0.15 коп.
  └─ Ad A: actual_spend=0.15 → 0.15 > 0 ❌ BLOCKED!

Батч #2 (00:00):
  ├─ max_allowed = 0 (ще та ж година!)
  ├─ Ad A: actual_spend=0.15 > 0 ❌ BLOCKED
  ├─ Ad B: actual_spend=0.12 > 0 ❌ BLOCKED
  ├─ ... всі заблоковані ...
  └─ Виграють лише organic ads (budget=0)

Батч #3, #4, ... #58 (всі о 00:00):
  ├─ Всі платні ads заблоковані
  └─ Виграють лише organic ads
```

### Наслідки:

| Метрика | Очікується | Фактично | Проблема |
|---------|------------|----------|----------|
| **Paid impressions** | 3.6% | 98.5% | У 27 разів більше! |
| **Organic impressions** | 96.4% | 1.5% | У 64 рази менше! |
| **N stability** | Зменшується | 81 весь день | Не зменшується |

**Пояснення:** Платні ads заблоковані вже о 00:00, тому показуються органічні (але їх лише 33 замість 5,090).

### Можливі рішення:

**Варіант 1: Мінімальний threshold**
```python
MIN_THRESHOLD = 0.05 * daily_budget  # 5% бюджету

expected_spend = max(daily_budget * time_progress, MIN_THRESHOLD)
max_allowed = expected_spend * (1 + pacing_tolerance)

# О 00:00:
max_allowed = max(0, 5 коп.) * 1.2 = 6 коп. ✅
```

**Варіант 2: Відключити pacing для hour=0**
```python
if hour == 0:
    return True  # Завжди дозволено в першій годині
```

**Варіант 3: Поминутне time_progress**
```python
minute = hour * 60 + current_minute
time_progress = minute / (24 * 60)

# О 00:05:
time_progress = 5 / 1440 = 0.0035
expected_spend = 100 × 0.0035 = 0.35 коп. ✅
```

### Статус:

✅ **ВИПРАВЛЕНО** в change `fix-pacing-gate-hour-zero`
📝 **Рішення:** Додано `min_time_progress_threshold` параметр

**💻 Код (ПІСЛЯ ФІКСУ):**

```python
# Локація: auction_engine.py:85-90
safe_time_progress = max(time_progress, self.min_time_progress_threshold)
expected_spend = ad.daily_budget * safe_time_progress  # Використовується safe_time_progress!
max_allowed = expected_spend * (1 + self.pacing_tolerance)

is_eligible = ad.actual_spend <= max_allowed
```

**📊 Результат:**
- Paid impressions: 98.5% → ~3.6% ✅ (27x correction)
- Organic impressions: 1.5% → ~96.4% ✅ (64x correction)
- N decreases naturally ✅ (не застряє на 81)

**🔗 Пов'язані питання:**
- [Що таке time_progress?](#time_progress-і-time_left)
- [Що таке pacing_tolerance?](#pacing_tolerance)
- [Що таке min_time_progress_threshold?](#min_time_progress_threshold)

**📖 Джерела:**
- Proposal: [fix-pacing-gate-hour-zero/proposal.md](../../openspec/changes/fix-pacing-gate-hour-zero/proposal.md)
- Spec delta: [fix-pacing-gate-hour-zero/specs/auction-engine/spec.md](../../openspec/changes/fix-pacing-gate-hour-zero/specs/auction-engine/spec.md)

**📅 Додано:** 2026-01-30

---

## max_allowed (pacing limit)

**🏷️ Теги:** `pacing`, `budget`, `limit`

**❓ Питання:**
Що таке max_allowed і як він обмежує витрати?

**💡 Коротка відповідь:**
**max_allowed** = максимальна сума яку може витратити оголошення на даний момент

**📚 Детальна відповідь:**

### Формула:

```python
expected_spend = daily_budget × time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

### Приклад (daily_budget=100 коп., pacing_tolerance=0.2):

| Час | time_progress | expected_spend | max_allowed | Графік |
|-----|---------------|----------------|-------------|--------|
| 00:00 | 0.0 | 0 коп. | **0 коп.** |  |
| 02:00 | 0.083 | 8.3 коп. | **10 коп.** | ██ |
| 06:00 | 0.25 | 25 коп. | **30 коп.** | ██████ |
| 12:00 | 0.5 | 50 коп. | **60 коп.** | ████████████ |
| 18:00 | 0.75 | 75 коп. | **90 коп.** | ██████████████████ |
| 23:00 | 0.958 | 95.8 коп. | **115 коп.** | ███████████████████████ |

### Як використовується:

**В кожному батчі перед аукціоном:**

```python
# Перевірка для кожного оголошення:
if ad.actual_spend <= max_allowed:
    # Дозволено участвувати
    pressure = calculate_pressure(ad)
else:
    # Заблоковано
    pressure = 0  # Не бере участі в аукціоні
```

### Приклад роботи:

**Оголошення X (daily_budget=100 коп.):**

| Батч | Час | actual_spend | max_allowed | Статус |
|------|-----|--------------|-------------|--------|
| 1 | 06:00 | 0 коп. | 30 коп. | ✅ OK (0 < 30) |
| 2 | 06:01 | 0.15 коп. | 30 коп. | ✅ OK (0.15 < 30) |
| 10 | 06:09 | 1.5 коп. | 30 коп. | ✅ OK (1.5 < 30) |
| ... | 06:30 | 25 коп. | 30 коп. | ✅ OK (25 < 30) |
| 200 | 06:55 | 31 коп. | 30 коп. | ❌ BLOCKED (31 > 30) |

**Оголошення заблоковано до наступної години (07:00), коли max_allowed = 35 коп.**

### Візуалізація:

```
Budget (коп.)
    120 ┤                                              ╱ max_allowed
        │                                          ╱
    100 ┤                                      ╱       daily_budget (лінія)
        │                                  ╱
     80 ┤                              ╱
        │                          ╱
     60 ┤                      ╱      ✅ Дозволена зона
        │   ✅ OK          ╱
     40 ┤              ╱
        │   ❌ BLOCKED
     20 ┤          ╱
        │      ╱
      0 ┼──────┬──────┬──────┬──────┬──────┬──────┬
        0h     4h     8h     12h    16h    20h    24h
```

**💻 Код:**

```python
# Локація: auction_engine.py:83-92
expected_spend = ad.daily_budget * time_progress
max_allowed = expected_spend * (1 + self.pacing_tolerance)

is_eligible = ad.actual_spend <= max_allowed

if not is_eligible:
    logger.debug(f"Ad {ad.ad_id} paused by pacing gate: "
                 f"spend={ad.actual_spend:.2f} > max_allowed={max_allowed:.2f}")

return is_eligible
```

**🔗 Пов'язані питання:**
- [Що таке pacing_tolerance?](#pacing_tolerance)
- [Проблема hour=0](#проблема-hour0)

**📖 Джерела:**
- Spec: [auction-engine/spec.md:69-92](../../openspec/specs/auction-engine/spec.md#L69-L92)

**📅 Додано:** 2026-01-30

---

## min_time_progress_threshold

**🏷️ Теги:** `pacing`, `threshold`, `hour-zero`, `safety`, `fix`

**❓ Питання:**
Що таке min_time_progress_threshold і чому він потрібен?

**💡 Коротка відповідь:**
**min_time_progress_threshold** = мінімальне значення для time_progress (0.042 = 1 година) — запобігає блокуванню ads о 00:00.

**📚 Детальна відповідь:**

### Проблема яку вирішує:

О 00:00, `time_progress=0.0` → `max_allowed=0` → будь-які витрати блокуються!

### Рішення (симетричне до min_time_left_threshold):

```python
safe_time_progress = max(time_progress, min_time_progress_threshold)
expected_spend = daily_budget × safe_time_progress
max_allowed = expected_spend × (1 + pacing_tolerance)
```

### Приклад (daily_budget=100 коп., threshold=0.042):

| Година | time_progress | safe_progress | max_allowed | Коментар |
|--------|---------------|---------------|-------------|----------|
| 0 | 0.000 | **0.042** | 5.04 коп. | ✅ Threshold застосовується! |
| 1 | 0.042 | 0.042 | 5.04 коп. | Threshold = реальне значення |
| 6 | 0.250 | 0.250 | 30.0 коп. | Threshold НЕ застосовується |
| 12 | 0.500 | 0.500 | 60.0 коп. | Threshold НЕ застосовується |

### Чому threshold=0.042?

- `0.042 = 1/24` (1 година)
- Симетричний до min_time_left_threshold
- О hour 1: `time_progress = 1/24 = 0.042` (threshold = мінімальне реальне значення)
- Дозволяє витратити ~5% бюджету в першій годині (з tolerance=0.2)

### Порівняння ДО і ПІСЛЯ:

| Метрика | БЕЗ threshold | З threshold=0.042 | Поліпшення |
|---------|---------------|-------------------|------------|
| **max_allowed о 00:00** | 0.00 коп. | 5.04 коп. | ∞ (з нуля!) |
| **Wins о 00:00** | 1 батч | ~33 батчі | 33x більше |
| **Paid impressions** | 98.5% | ~3.6% | 27x корекція |
| **Organic impressions** | 1.5% | ~96.4% | 64x корекція |

**💻 Код:**

```python
# Локація: auction_engine.py:85-90
# Apply minimum threshold to prevent zero max_allowed at hour 0
# NOTE: At hour 0, time_progress=0.0 < 0.042, so threshold is applied
# This allows ads to spend ~5% of budget in first hour
safe_time_progress = max(time_progress, self.min_time_progress_threshold)

expected_spend = ad.daily_budget * safe_time_progress
max_allowed = expected_spend * (1 + self.pacing_tolerance)
```

**⚙️ Конфігурація:**

```yaml
# config/local.yaml
simulation:
  min_time_progress_threshold: 0.042  # 1 hour = 1/24
```

**🔗 Пов'язані питання:**
- [Проблема hour=0](#проблема-hour0) (яку це вирішує)
- [Що таке min_time_left_threshold?](#min_time_left_threshold) (симетричний патерн)
- [Що таке time_progress?](#time_progress-і-time_left)

**📖 Джерела:**
- Proposal: [fix-pacing-gate-hour-zero/proposal.md](../../openspec/changes/fix-pacing-gate-hour-zero/proposal.md)
- Spec: [fix-pacing-gate-hour-zero/specs/auction-engine/spec.md](../../openspec/changes/fix-pacing-gate-hour-zero/specs/auction-engine/spec.md)
- Test: [test_pacing_comparison.py](../../test_pacing_comparison.py)

**📅 Додано:** 2026-01-30

---

[⬅️ Назад до індексу](./README.md)
