# Skill: Add a New Report

## Purpose
Create a new report following the Template Method pattern with RBAC, export, and audit logging.

## When to Use
- Adding a new daily/weekly/monthly/on-demand report
- Adding a new export format for existing data

## Steps
1. Create report generator class inheriting BaseReportGenerator in reports.py
2. Implement _query_data() and _format_output()
3. Register in report_service.py with required permission
4. Add Gradio view (table + filters + download button)
5. Add CSV export via pandas to_csv() + gr.File()
6. Add RBAC permission check
7. Write unit test for query and filter logic
8. Update role defaults if needed

## Template Method Pipeline (base class enforces)
1. Authenticate → 2. Verify permission → 3. Query → 4. Filter → 5. Format → 6. Audit log

## Conventions
- Same visual pattern: data table + filters + download
- Date range max: 90 days, default sort: date descending
- Every view/download is audit logged
