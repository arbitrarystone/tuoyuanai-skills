# Contributing

Keep this repository a thin client of TuoyuanAI's current canonical API.
Do not copy platform-private source, provider secrets, customer data or acceptance accounts.
Do not add old-protocol adapters, automatic paid retries, global project rebinding or example-specific behavior.

Discuss API changes before implementing them. Document any change in permissions, cost, persistence or command output.
Use only Python's standard library unless a new dependency is clearly justified.

Acceptance must use a complete platform deployment and a visible Playwright browser
(`headless=false`) to verify CLI actions appear on the same user's canvas and survive reload.
Use isolated acceptance accounts; never turn local test data into claims about production data.
Do not submit video generation during acceptance without explicit authorization; use the platform's
mock video provider if that workflow needs coverage. Record exactly which paths were exercised and
which were not. Do not publish credentials, raw signed URLs, customer outputs or unredacted screenshots.
