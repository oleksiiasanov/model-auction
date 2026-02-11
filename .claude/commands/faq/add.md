---
name: FAQ: Add Entry
description: Add a new Q&A entry to the auction simulator FAQ documentation.
category: Documentation
tags: [faq, documentation, qa]
---

**Purpose**: Add a new question and answer to the FAQ system in a structured format.

**Steps**:
1. **Determine the section**: Ask user which section (if not obvious):
   - `01-terminology.md` - Basic terms and definitions (N, pressure, rank_index, etc.)
   - `02-auction-mechanics.md` - How auctions work (formulas, calculations, algorithms)
   - `03-pacing-gate.md` - Pacing mechanism (time_progress, tolerance, thresholds)
   - `04-budget-calculation.md` - Budget management and spending
   - `05-configuration.md` - Configuration parameters and tuning
   - `06-troubleshooting.md` - Common problems and solutions

2. **Format the entry** following this template:
   ```markdown
   ## [Short title]

   **🏷️ Теги:** `tag1`, `tag2`, `tag3`

   **❓ Питання:**
   [Full question as user would ask it]

   **💡 Коротка відповідь:**
   [1-2 sentences, direct answer]

   **📚 Детальна відповідь:**

   ### [Section heading if needed]

   [Detailed explanation with examples, formulas, or step-by-step procedures]

   **💻 Код:**

   ```python
   # Локація: file.py:line-range
   [relevant code snippet]
   ```

   **🔗 Пов'язані питання:**
   - [Link to related FAQ entry](#anchor)
   - [Link to spec](../../openspec/specs/...)

   **📖 Джерела:**
   - [Reference to spec, config, or code](path/to/file.ext#L123)

   **📅 Додано:** YYYY-MM-DD

   ---
   ```

3. **Add the entry**:
   - Read the target section file
   - Add the new entry before the final "Назад до індексу" link
   - Use Edit tool to insert the new content

4. **Update statistics** in [docs/faq/README.md](auction-simulator/docs/faq/README.md):
   - Increment the count for the section
   - Update last updated date

5. **Verify formatting**:
   - Check that all links work (use relative paths)
   - Ensure code blocks have proper language tags
   - Verify cross-references use correct anchors

**Guidelines**:
- Use **Ukrainian** for all text content
- Include **code snippets** with file locations (e.g., `# Локація: auction_engine.py:63-65`)
- Add **examples** with real values from the codebase
- Cross-reference related FAQ entries for navigation
- Use **emojis** consistently (🏷️ tags, ❓ question, 💡 short, 📚 detailed, 💻 code, 🔗 links, 📖 sources, 📅 date)
- Keep **short answers** concise (1-2 sentences maximum)
- Make **detailed answers** comprehensive with subsections, tables, or visualizations as needed

**Example usage**:
```
User: /faq-add
Assistant: Яке питання потрібно додати? До якого розділу?
User: Чому pressure стає 0 коли budget закінчується? Додай до terminology
Assistant: [Follows steps above to add entry to 01-terminology.md]
```
