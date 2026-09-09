# Contributing

This is a three-person capstone project. The workflow below is deliberately small -- enough to keep `main` healthy and to make sure a human understands everything that merges.

## Workflow at a glance

```
Issue -> assignment -> branch -> implement and test -> Pull Request -> teammate review -> merge -> Done
```

Routine work does not happen on `main`.

## Starting work

Implementation work starts from an Issue. Before making project changes:

1. Make sure an Issue exists and says what "done" means.
2. Assign it to yourself, so two people do not build the same thing.
3. Branch from an up-to-date `main`.

If an Issue is ambiguous, say so on the Issue and get it clarified. Do not guess at the requirements.

## Branches

Use `<type>/<short-description>` -- for example, `docs/bootstrap-project-docs`.

Types are short and descriptive, such as `feat`, `fix`, `docs`, or `chore`. Keep the description lowercase and hyphenated. Keep branches short-lived and scoped to one Issue whenever practical. Merge and delete them when the work is complete.

## Commits

Write clear, descriptive commit messages that say what changed -- "Add expense model", not "changes" or "wip". Prefer a few small commits that each stand on their own over one large commit that does everything.

There is no required commit-message format beyond being clear.

## Pull requests

Open a pull request against `main` when the work is ready for someone else to read. The description should answer:

- **Which Issue does this close?** Use `Closes #N` so GitHub links it and closes it on merge.
- **What changed, and why?**
- **How was it checked?** Say what you actually ran.

**Suggested pull request description:**

Replace `N` with the Issue number the pull request closes.

```
## Summary

Briefly explain what changed and why. A short description and/or list of file changes is enough.

## Validation

- List the checks, tests, or manual verification you actually performed.
- Do not claim a check passed unless you ran it.

Closes #N
```
Keep pull requests small enough that a teammate can genuinely review them.

## Review

Every pull request gets a review from a teammate before it merges. The reviewer's job is to understand the change, not to rubber-stamp it -- if you cannot explain what a pull request does, that is a reason to ask questions, not to approve it.

The author is responsible for addressing review feedback and understanding the final change that is merged.

## AI-assisted contributions

We use AI coding agents on this project, and agent-produced changes follow exactly the same path: Issue, branch, pull request, teammate review. There is no fast lane.

The person who opens the pull request owns the change and must understand it well enough to defend it in review. Code that nobody on the team understands does not merge.

## After merge

Delete the merged branch. If the pull request used `Closes #N`, GitHub will close the Issue automatically when the PR merges. Otherwise, confirm the Issue is complete and close it manually.

## Not set up yet

Continuous integration, pull request and Issue templates, and a label taxonomy are not in place. They will be documented here if and when the team adopts them.
