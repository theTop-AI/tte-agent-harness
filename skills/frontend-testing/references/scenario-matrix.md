# Frontend scenario matrix

Use one row per kind for every acceptance criterion that has a screen. Skip a kind only with a
reason written in the coverage note.

| Kind | What to prove | Typical level |
|---|---|---|
| positive | the screen shows the contract's data, correctly formatted | component, E2E |
| empty | the empty state and its call to action when the list is empty | component |
| negative | the error state for each contract error (4xx with `code`, 5xx, network failure) | integration |
| boundary | first and last page, maximum page size, longest values, zero and large numbers | component |
| permission | a user without the permission sees the denied state, and the action is absent | E2E |
| isolation | data of another tenant never appears, even when the mock returns it by mistake | integration |
| accessibility | roles and names, keyboard path, focus after navigation, no axe violations if the repo checks them | component, E2E |
| freshness | numbers show the freshness the contract returns (tte-frontend `meta.freshness`) | component |
| regression | the bug that prompted the change stays fixed | lowest level that reproduced it |

## Test-first checklist

- [ ] The test names the AC id.
- [ ] It fails before the implementation for the expected reason (missing element or route).
- [ ] It uses fixtures generated from or checked against the pinned contract.
- [ ] It waits for visible states, never for a fixed time.
