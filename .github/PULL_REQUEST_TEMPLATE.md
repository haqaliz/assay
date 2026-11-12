<!-- Thanks for contributing to Assay. Keep PRs focused. See CONTRIBUTING.md. -->

## What and why

<!-- What does this change, and why? Link the issue if there is one (Closes #N). -->

## How it was tested

<!-- The tests you added or ran. Sandbox tests require macOS. -->

```sh
uv run pytest
```

## Checklist

- [ ] Test-first: a failing test captured the behavior, then the code made it pass.
- [ ] `uv run pytest` is green.
- [ ] Docs updated if behavior or the public surface changed.
- [ ] No secrets, private audit records, or real user data committed.
- [ ] No new dependency unless justified in the PR.
- [ ] The four-class severity floor and the instruction `REVIEW` cap are unchanged, or the change
      was discussed explicitly.
- [ ] No static-only or model-only verdict was introduced; `UNVERIFIED` is not treated as a pass.
- [ ] MCP/audit changes stay evidence-only unless a design note says otherwise.
