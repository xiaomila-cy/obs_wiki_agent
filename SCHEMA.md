# Wiki Schema

## Domain
信息安全，涵盖：
- 数据安全（分类分级、加密、脱敏、DLP）
- 个人信息保护（个保法、PIPL、GDPR 合规）
- 汽车安全合规（UN R155/R156、GB 标准、VTA/CSMS）
- 企业安全建设（SDL、零信任、SOC、应急响应）
- 网络安全（等保、关基、渗透测试）

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
