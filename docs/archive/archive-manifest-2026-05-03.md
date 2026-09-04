# Archive Manifest 2026-05-03

목적: `docs/README.md`를 현재 Plan Rebase 구조에 맞게 한글화하면서 루트에 남아 있던 과거 전환 증적 문서를 아카이브로 이동했다.

## 이동 대상

### Legacy tuning 증적

- `docs/2026-04-16-holding-profit-conversion-plan.md` -> `docs/archive/legacy-tuning-2026-04-06-to-2026-04-20/2026-04-16-holding-profit-conversion-plan.md`
- `docs/2026-04-17-midterm-tuning-performance-report.md` -> `docs/archive/legacy-tuning-2026-04-06-to-2026-04-20/2026-04-17-midterm-tuning-performance-report.md`
- `docs/2026-04-18-nextweek-validation-axis-table-audited.md` -> `docs/archive/legacy-tuning-2026-04-06-to-2026-04-20/2026-04-18-nextweek-validation-axis-table-audited.md`

### Plan Rebase 전환 증적

- `docs/2026-04-20-auditor-third-review.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-20-auditor-third-review.md`
- `docs/2026-04-20-operator-response.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-20-operator-response.md`
- `docs/2026-04-20-postclose-audit-result-report.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-20-postclose-audit-result-report.md`
- `docs/2026-04-21-auditor-performance-result-report.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-21-auditor-performance-result-report.md`
- `docs/2026-04-21-plan-rebase-auditor-report.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-21-plan-rebase-auditor-report.md`
- `docs/2026-04-22-auditor-performance-result-report.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-22-auditor-performance-result-report.md`
- `docs/2026-04-22-ai-generated-code-governance.md` -> `docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-22-ai-generated-code-governance.md`

### Reference/Runbook

- `docs/2026-04-11-github-project-google-calendar-setup.md` -> `docs/archive/reference-and-runbooks/2026-04-11-github-project-google-calendar-setup.md`

## 루트 유지 대상

- `2026-04-10-scalping-ai-coding-instructions.md`, `2026-04-11-scalping-ai-prompt-coding-instructions.md`: project parser가 직접 참조하는 고정 입력이므로 유지.
- `2026-04-20-stage2-todo-checklist.md` 이후 날짜별 checklist: 과거 실행 증적이지만 현재 Plan Rebase와 Project 동기화 추적성을 위해 유지.
- 2026-04-28 이후 acceptance/report/code-review 문서: 현재 또는 최근 checklist에서 직접 참조되므로 유지.

## 검증

- 이동 후 기존 Markdown 링크는 새 절대경로로 보정한다.
- 문서 변경 후 parser 검증 명령:

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
```
