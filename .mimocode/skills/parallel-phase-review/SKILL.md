---
name: parallel-phase-review
description: Spawn parallel subagents to review code implementation phases and generate structured review reports.
---

# Parallel Phase Code Review

Spawn multiple subagents in parallel to review code phases and produce structured review reports.

## When to Use

- User requests review of multiple implementation phases simultaneously
- User references "review song song" or "parallel review" of phases
- User wants reports "tương tự các phase" (similar to existing phase reports)

## Procedure

### 1. Discover Existing Reports

Read existing `review-report.md` files under `implementation/phase*/` to understand:
- The report format and structure already in use
- What phases have already been reviewed
- The severity categories and section layout

### 2. Explore Project Structure

Spawn an **explore subagent** to map the codebase:
- Read `backend/app/` directory structure
- Identify all Python modules and their relationships
- Note existing patterns (models, services, API layers, etc.)

### 3. Spawn Review Subagents (One Per Phase)

For each phase to review, spawn a **general subagent** with this prompt template:

```
You are reviewing Phase {N} ({PHASE_NAME}) implementation for a document operations agent project.

Your task is to review all code files in {FILE_PATHS}.

For each file:
1. Read the full file content
2. Assess code quality, correctness, and adherence to clean architecture
3. Identify issues by severity: Critical (must fix), Major (should fix), Minor (nice to have), Info
4. Note what was done well

Produce a structured review report in the exact format of the existing phase review reports under implementation/phase*/review-report.md. Save the report to: implementation/phase{N}-{slug}/review-report.md

Return format:
**Status**: success | partial | failed
**Summary**: <one-line description>
**Files touched**: <paths>
```

### 4. Wait and Collect Results

After spawning all review subagents:
- Wait for each to complete
- Read the generated review reports
- Summarize cross-phase findings if requested

### 5. Report

Present a summary table:

| Phase | Verdict | Critical | Major | Minor | Files Reviewed |
|-------|---------|----------|-------|-------|----------------|

## Output Format

Each review report follows the established structure:
- Header with reviewer, date, scope, overall assessment
- File-by-file review with quality rating
- Issues table (severity, location, description)
- Summary of critical/major/minor issues
- What was done well

## Stopping Condition

All requested phase review reports are written to `implementation/phase*/review-report.md` and the summary table is presented to the user.
