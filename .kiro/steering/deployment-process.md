---
inclusion: auto
---

# Deployment Process

## Environments
| Environment | Platform | Purpose | Config Source |
|-------------|----------|---------|---------------|
| Local dev | Developer machine | Unit/property tests | `.env.local` |
| CI | GitHub Actions runner | All automated tests | GitHub Secrets |
| Staging | HF Space (separate) | E2E + DAST testing | HF Space Secrets (staging) |
| Production | HF Space (main) | Live application | HF Space Secrets (prod) |

## Portal Deployment (Automated)
1. PR merged to main → CI triggers
2. Lint → type-check → unit → property → integration → architecture → security
3. Deploy to staging
4. E2E tests + DAST scan against staging
5. If pass → deploy to production
6. Post-deploy smoke test

## Tracker Build (On Release Tag)
1. Tag release (e.g., tracker-v1.2.3)
2. Matrix build: Windows (.exe) + macOS (.app)
3. Sign + notarize executables
4. Attach to GitHub Release

## Tracker Installation (Per Employee)
1. HR adds employee in Portal → Employee_ID generated
2. HR downloads pre-configured installer
3. IT installs (admin rights required)
4. macOS: grant Accessibility permission
5. Verify heartbeat in Google Sheets

## Rollback
- Portal: revert Git commit → auto-redeploy
- Tracker: distribute previous release
- Data: Google Sheets version history

## Required Secrets
| Secret | Where | Purpose |
|--------|-------|---------|
| GOOGLE_SERVICE_ACCOUNT_JSON | HF Secrets + Tracker | Sheets API auth |
| GEMINI_API_KEY | HF Secrets | AI tagging |
| EMAIL_API_KEY | HF Secrets | Magic links |
| HF_TOKEN | GitHub Secrets | Deploy to HF |
| SNYK_TOKEN | GitHub Secrets | Security scan |
| APPLE_DEVELOPER_ID | GitHub Secrets | macOS signing |
| WINDOWS_SIGN_CERT | GitHub Secrets | Windows signing |
