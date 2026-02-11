# 📚 Auction Simulator FAQ

Frequently Asked Questions про механіку роботи аукційного симулятора.

## 📖 Розділи

### [01. Термінологія](./01-terminology.md)
Базові терміни та концепції аукційної системи.

| Питання | Складність |
|---------|-----------|
| [Різниця між Reach, Impressions і Unique Users](./01-terminology.md#різниця-між-reach-impressions-і-unique-users) | 🟢 Базова |
| [Що таке N і чому він дорівнює 81?](./01-terminology.md#що-таке-n) | 🟢 Базова |
| [Різниця між effective_bid і min_bid](./01-terminology.md#різниця-між-effective_bid-і-min_bid) | 🟢 Базова |
| [Що таке pressure?](./01-terminology.md#що-таке-pressure) | 🟡 Середня |
| [Що таке rank_index?](./01-terminology.md#що-таке-rank_index) | 🟢 Базова |

### [02. Механіка аукціону](./02-auction-mechanics.md)
Як працює аукціон, формули розрахунку ставок.

| Питання | Складність |
|---------|-----------|
| [Як розраховується effective_bid?](./02-auction-mechanics.md#як-розраховується-effective_bid) | 🟡 Середня |
| [N=300 чи N=40 коли 300 ads, 40 slots?](./02-auction-mechanics.md#n300-чи-n40) | 🔴 Складна |
| [Чому формула (N-1-rank) а не просто rank?](./02-auction-mechanics.md#чому-формула-n-1-rank) | 🟡 Середня |

### [03. Pacing Gate](./03-pacing-gate.md)
Механізм контролю темпу витрат бюджету.

| Питання | Складність |
|---------|-----------|
| [Що таке time_progress і time_left?](./03-pacing-gate.md#time_progress-і-time_left) | 🟡 Середня |
| [Що таке pacing_tolerance?](./03-pacing-gate.md#pacing_tolerance) | 🟡 Середня |
| [Навіщо min_time_left_threshold?](./03-pacing-gate.md#min_time_left_threshold) | 🔴 Складна |
| [Чому pacing gate блокує все о 00:00?](./03-pacing-gate.md#проблема-hour0) | 🔴 Складна |

### [04. Бюджети та витрати](./04-budget-calculation.md)
Розрахунок бюджетів, витрат, копійок.

### [05. Конфігурація](./05-configuration.md)
Питання про налаштування симулятора.

### [06. Проблеми та рішення](./06-troubleshooting.md)
Поширені проблеми та способи їх вирішення.

### [07. Витягування даних](./07-data-extraction.md)
Питання про витягування даних з бази, бюджети, impressions.

| Питання | Складність |
|---------|-----------|
| [Чому кількість бюджетів в базі не співпадає з симуляцією?](./07-data-extraction.md#чому-кількість-оголошень-з-бюджетом-в-базі-не-співпадає-з-симуляцією) | 🟡 Середня |
| [Чому різні campaign_id для одного ad_id?](./07-data-extraction.md#чому-spendings_distributed-має-більше-записів-ніж-унікальних-ad_id) | 🟢 Базова |
| [Чому симуляція витягує менше бюджету?](./07-data-extraction.md#чому-симуляція-витягує-менше-бюджету-ніж-показує-dbeaver) | 🟡 Середня |
| [Чому в симуляції більше paid ads/sellers?](./07-data-extraction.md#чому-в-симуляції-більше-paid-adssellers-ніж-в-actual-data) | 🟡 Середня |

---

## 🔍 Швидкий пошук

**За тегами:**
- [`#terminology`](./01-terminology.md) - Базові терміни
- [`#auction`](./02-auction-mechanics.md) - Механіка аукціону
- [`#pacing`](./03-pacing-gate.md) - Контроль темпу
- [`#budget`](./04-budget-calculation.md) - Бюджети
- [`#config`](./05-configuration.md) - Конфігурація
- [`#data-extraction`](./07-data-extraction.md) - Витягування даних

**За складністю:**
- 🟢 Базова - для початківців
- 🟡 Середня - потрібне розуміння системи
- 🔴 Складна - глибокі технічні деталі

---

## ➕ Як додати нове питання?

### Спосіб 1: Вручну
Скажіть мені: "Додай це до FAQ у розділ [назва]"

### Спосіб 2: Через skill
```
/faq-add category=terminology difficulty=basic
```

---

## 📊 Статистика

- **Всього питань:** 15
- **Останнє оновлення:** 2026-02-05
- **Додано у цій сесії:** 5

---

## 🔗 Пов'язані ресурси

- [Специфікація auction-engine](../../openspec/specs/auction-engine/spec.md)
- [Конфігурація](../../config/local.yaml)
- [Вихідний код](../../src/auction_simulator/)
