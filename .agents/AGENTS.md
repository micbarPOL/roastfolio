
## Git Commits
- All commits must have proper, descriptive commit messages explaining the 'why' and 'what'.
- If doing multiple things, divide the changes into separate commits so they can be easily reverted.

## Branching Strategy
- By default, you should commit and push changes to the `dev` branch, and then merge and push them to the `test` branch.
- You must wait for explicit permission from the user before merging and pushing to the `prod` branch.

## Release Versioning & Deployment
- When deploying/pushing changes to `dev` (and subsequently `test` or `prod`), ALWAYS bump the version according to the release numbering policy:
  - **Major version (`X.0.0`)**: Brand-new user-facing features, tools, screens, or major architectural additions. Resets Minor and Service to 0.
  - **Minor version (`X.Y.0`)**: Changes, refinements, redesigns, or enhancements to existing features. Resets Service to 0.
  - **Service release (`X.Y.Z`)**: Bug fixes, performance improvements, and corrections. Increments Service by 1.
- Keep the version synchronized across all UI displays (`src/index.html`, `src/guide.html`, `src/auth.html`), `package.json`, documentation (`docs/RELEASE_NUMBERING.md`), and contract tests (`tests/test_footer_and_release_contract.py`).

## Testing Strategy & Authentication Rules
- **Smoke Tests (`./test.sh smoke` / `npm run test:smoke`)**:
  - MUST be executed after any UI, layout, CSS, HTML, brand, or template change. Runs contract tests in under 1 second.
- **Full Tests (`./test.sh full` / `npm run test:full`)**:
  - Must be executed after backend calculation, financial math (XIRR/AVCO), schema, or API handler changes.
- **No User Creation or Password Resets in Tests**:
  - NEVER create live Cognito users, send verification emails, or perform password reset flows for UI testing.
  - Always use the instant mock auth bypass: `?devAuth=1` or `localStorage.setItem('roastfolio.devAuth', '1')` as implemented in `src/scripts/auth-guard.js`.

