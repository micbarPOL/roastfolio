
## Git Commits
- All commits must have proper, descriptive commit messages explaining the 'why' and 'what'.
- If doing multiple things, divide the changes into separate commits so they can be easily reverted.

## Branching Strategy
- You may merge and push changes to the `test` or `prod` branches when explicitly asked to do so by the user. By default, only commit and push directly to the `dev` branch.

## Release Versioning & Deployment
- When deploying/pushing changes to `dev` (and subsequently `test` or `prod`), ALWAYS bump the version according to the release numbering policy:
  - **Major version (`X.0.0`)**: Brand-new user-facing features, tools, screens, or major architectural additions. Resets Minor and Service to 0.
  - **Minor version (`X.Y.0`)**: Changes, refinements, redesigns, or enhancements to existing features. Resets Service to 0.
  - **Service release (`X.Y.Z`)**: Bug fixes, performance improvements, and corrections. Increments Service by 1.
- Keep the version synchronized across all UI displays (`src/index.html`, `src/guide.html`, `src/auth.html`), `package.json`, documentation (`docs/RELEASE_NUMBERING.md`), and contract tests (`tests/test_footer_and_release_contract.py`).
