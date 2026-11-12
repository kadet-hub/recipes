# Contributing

You can ask for a recipe, write or change one, or change `check` and CI.
All three end in a pull request, described at the end.

## Asking for a recipe

Open the form
[Request a recipe](https://github.com/kadet-hub/recipes/issues/new?template=recipe-request.yml)
with the application, the Helm chart or compose file a recipe would
rebuild, and what you need it for. Open requests are listed on
[kadet-hub.org/wanted](https://kadet-hub.org/wanted/), most 👍 first. If
your application is there already, add a 👍 to that request.

A problem with a recipe or a question goes into an issue. A vulnerability
goes through private reporting, as [SECURITY.md](SECURITY.md) describes.

## Writing or changing a recipe

A change starts with the spec. Each recipe has its own section in
[docs/specs/recipes.md](docs/specs/recipes.md) with its decisions (`DEC-n`)
and requirements (`RCP-n`). The first commit of the pull request adds or
edits that section, with the next free IDs. IDs are never renumbered, and
[docs/specs/README.md](docs/specs/README.md) describes the format. The
ntfy recipe, [#161](https://github.com/kadet-hub/recipes/pull/161), is a
recent example: a spec commit, the recipe, and a last commit that sets
`Since:` to the pull request's number.

The spec's sections "Layout" and "Writing a recipe" say which files a
recipe has and how they are written. [Adding a recipe](README.md#adding-a-recipe)
in the README lists the `check` commands that prove it and the tools they
need. In the pull request, say which of them you ran and paste the report
that `check` printed.

When the chart behind a recipe has a new release, Renovate opens a pull
request that moves only the README's `Source` line. Its `check` fails, and
the report shows what the new chart renders differently (RCP-16). The
recipe follows in a separate pull request that moves its images and values.

## Changing check or CI

`check` is a uv project in `check/`. Its unit tests need no cluster:

```sh
uv run --locked --project check python -m unittest discover -s check/tests -t check -v
```

A change under `check/` outside `check/tests/` raises `VERSION` in
`check/check.py`, or the CI job `version` fails (RCP-406). The registry
gate and the `to-recipe` skill run a tagged `check` release, so the new
version reaches them once the maintainer tags it (RCP-22). A requirement
you add or change names its check in the `Test:` line. CI also runs
actionlint and zizmor on the workflows and pip-audit on `check/uv.lock`.

## Pull requests

Open the pull request from a fork. Only maintainers and Renovate push
branches to this repository. Titles and commits follow Conventional
Commits, as in the history: `feat: ntfy recipe`, `fix(zulip): ...`,
`fix(check): ...`. Commits here carry a `Signed-off-by` line
(`git commit -s`). Please add one, although no check enforces it.

The first workflow run of a new contributor waits until a maintainer
approves it. CI then lints and checks every recipe the pull request
changes, and every recipe that includes a changed one, at the level its
README states, on the three Kubernetes minors of RCP-70. The `deploys`
proof runs the fork's manifests on the runner, so on a fork it waits for a
maintainer's approval once more (RCP-20). The job `ci` sums up all other
jobs and is the one required check (RCP-65).

`neat-bot`, a review bot with read access, reviews every pull request. On
a fork a maintainer requests it after a first look (RCP-57). Its approval
does not count toward the merge. A pull request merges once `ci` passed
and a maintainer approved it, and a push after the approval dismisses it.

After the merge the maintainer tags the recipe's release `<name>-vX.Y.Z`
(RCP-31) and registers it in kadet-hub/registry, whose gate checks the
recipe again before the release is published.
