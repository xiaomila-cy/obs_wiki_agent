# Wiki Schema

## Domain
王哥的个人知识库，分为 5 个板块（在 `domains.json` 管理，随时可增删）：

| 板块 | ID | 覆盖内容 |
|------|-----|---------|
| 🔐 IT网络与数据安全 | `it-security` | 等保、关基、数据分类分级、个保法、应急响应 |
| 🚗 智能网联汽车安全 | `auto-security` | UN R155/R156、ISO 21434、GB国标、CSMS/VTA |
| 📈 投资之路 | `investment` | A股投资、个股分析、基金持仓、交易策略 |
| 📝 日常记录 | `daily` | 日常想法、随手记录、读书笔记 |
| 🤖 AI学习 | `ai-learning` | 大模型、Agent开发、Prompt工程、AI工具 |

每页的 `domain` 字段对应上面的 ID，不填则通过标签自动归类。

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `personal-information-protection-law.md`)
- Every wiki page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md` under the correct section
- Every action must be appended to `log.md`
- Provenance: On pages synthesizing 3+ sources, append `^[raw/xxx.md]` markers

## Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [from taxonomy below]
sources: [raw/articles/source-name.md]
confidence: high | medium | low
contested: true
contradictions: [other-page-slug]
---
```

## Tag Taxonomy
- **法规标准**: regulation, standard, compliance, certification
- **技术**: encryption, network-security, app-security, cloud-security, endpoint
- **管理**: risk-management, audit, incident-response, governance
- **行业**: automotive, finance, healthcare, telecom
- **个人信息**: privacy, consent, cross-border, data-subject-rights
- **汽车安全**: csms, vta, sums, iso21434, un-r155, un-r156
- **攻防**: threat-modeling, penetration-test, vulnerability, apt
- **Meta**: comparison, timeline, controversy, opinion

Rule: every tag on a page must appear in this taxonomy. Add new tags here first.

## Page Thresholds
- Create a page when an entity/concept appears in 2+ sources OR is central
- DON'T create for passing mentions
- Split a page when it exceeds ~200 lines
- Archive when fully superseded

## Entity Pages
Companies, regulators, standards bodies, key persons:
- Overview
- Key facts and dates
- Relationships ([[wikilinks]])
- Source references

## Concept Pages
Regulations, technical concepts, frameworks:
- Definition
- Current state
- Open questions
- Related concepts

## Comparison Pages
Side-by-side analyses (e.g., PIPL vs GDPR, ISO 21434 vs UN R155)

## Update Policy
- Newer sources supersede older
- Conflicting info → note both with dates, mark contested
- Flag contradictions for review
