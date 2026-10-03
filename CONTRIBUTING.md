# Contributing to oterm

Bug reports, fixes and documentation are welcome. For features, start with an issue.

## Reporting issues

Open an issue at https://github.com/ggozad/oterm/issues. Describe what you did, what happened and what you expected. Include the `oterm` version, your terminal, the provider and model, and the relevant part of `config.json`.

## Before you start

Open an issue first for anything beyond a small fix, and describe how you plan to solve it. Wait until I agree with the plan in the issue before writing code. A plan nobody has answered is not an approval.

Pull requests without an agreed plan are closed without review.

## Development setup

```bash
git clone https://github.com/ggozad/oterm.git
cd oterm
uv sync
uv run pre-commit install
```

## Making changes

1. Create a branch from `main`.
2. Make your change, with tests. Coverage is enforced at 100%.
3. Run the checks:

   ```bash
   uv run pytest
   uv run ruff check && uv run ruff format
   uv run ty check
   ```

4. Run oterm with your change and use it. A passing test suite does not show that the feature works.
5. Add an entry under `[Unreleased]` in `CHANGELOG.md`.
6. Update `docs/` and `README.md` if you changed user-facing behaviour. Docs and changelog prose use no em dashes.
7. Open a pull request against `main`. Link the issue, say what changed and how you checked it. For anything visible, include a screenshot or recording.

The [Development guide](https://ggozad.github.io/oterm/development/) covers logs and debugging.

## AI-assisted contributions

oterm is older than AI tools that could write usable code, and I wrote it without them. Since the beginning of 2026 I use AI tools myself, and most new code is written with them. I never vibe-code, I keep control of the design, and I review and check everything they produce.

Using AI tools to write code, issues or pull requests is fine. What matters is that a human (you) has read the result and run it before I see it. I review everything myself, so I need to understand the problem and the solution from what you send.

- If you plan to use AI for the implementation, describe your plan in the issue and wait for my answer.
- Read, check and trim whatever the tool produced. Remove anything you cannot explain or that does not serve the change.
- Keep issues and pull request descriptions short and concrete. Say what is wrong, how you fixed it and how you verified it.
- Say that AI was used. It is not held against the contribution.

## Automated contributions

oterm is a tool for people who use it. Pull requests opened by automated agents, by contribution services, or by accounts that open pull requests across many projects without using them will be closed, and the account may be blocked.

## License

By contributing you agree that your contributions are licensed under the MIT License.
