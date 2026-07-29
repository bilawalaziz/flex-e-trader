# CLAUDE.md

Guidance for Claude Code (and any agent) working in this repository.

## Project overview

FlexiTrader is an energy flexibility optimisation platform: it ingests live market
prices, decides how to charge and discharge a portfolio of flexible assets, and
publishes the resulting schedules. See [README.md](README.md) for the domain
framing.

Layout under `app/`: `api/` (FastAPI routes), `consumers/` (message consumers),
`services/` (the optimiser and friends), `repositories/`, `models/`, `schemas/`,
`tasks/` (Celery), `core/`. Entry points are
[app/main.py](app/main.py) and [app/celery_app.py](app/celery_app.py).

## What the optimiser actually does

`app/services/optimisation.py` builds a battery dispatch LP with
`scipy.optimize.linprog` over 96 intervals. It solves the **relaxation** and then
repairs intervals where charge and discharge both come back non-zero, so the
published schedule is feasible but **not provably optimal**.
`flexetrader_lp_repaired_intervals_total` counts when that repair fires.

Replacing it with `scipy.optimize.milp` and binaries, and extending to
solar/wind/biogas as a multi-asset portfolio, are the two items still in the
README's own "future work" section. Don't describe either as done.

## Reproduce CI locally before pushing

A red remote after a push is a rule violation, not bad luck.
[CI](.github/workflows/ci.yml) has three jobs:

```bash
# lint — no services needed
pip install ruff==0.15.16      # pinned; see the comment in ci.yml
ruff check .
ruff format --check .

# test — needs postgres, rabbitmq and redis
docker compose up -d postgres rabbitmq redis
docker compose exec -T postgres pg_isready -U flexetrader   # wait for it
export DATABASE_URL=postgresql+asyncpg://flexetrader:flexetrader@localhost:5432/flexetrader
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head
pytest -v

# build
docker build -t flexetrader:latest .
```

**Two things in the CI file cannot be copy-pasted locally.** Both were hit while
writing this section, so take them at face value:

- **The Postgres password differs.** CI sets `POSTGRES_PASSWORD: secret`;
  `docker-compose.yml` sets `flexetrader`. Copying CI's `DATABASE_URL` verbatim
  gives an auth failure against the local container. The commands above use the
  compose password.
- **`pg_isready` is not installed on this host.** CI's
  `until pg_isready -h localhost …; do sleep 2; done` therefore loops **forever**
  rather than failing — it looks like a hung test run. Use
  `docker compose exec -T postgres pg_isready -U flexetrader`, which runs the
  binary inside the container where it exists.

The suite is fast once the services are up: **17 tests, ~2s**. The
`SAWarning: garbage collector is trying to clean up non-checked-in connection`
noise is pre-existing and not a failure.

**`ruff format --check .` is a separate CI job here** and is easy to forget — a
formatting-only diff that passes `ruff check` still reddens the build. Run both.

**But don't run `ruff format --check .` bare — it lies locally.** It walks the
whole working tree including the user's untracked scratch files, which CI never
checks out. `runit.py` currently fails it while all 55 tracked files pass, so the
bare command reports a failure that cannot happen on the remote. Check what CI
actually checks:

```bash
git ls-files '*.py' | xargs ruff format --check
```

The inverse trap is worse: never "fix" the reported file by reformatting it. It
is the user's scratch work, and reformatting or committing it is the actual
mistake.

**Ruff is pinned to 0.15.16** deliberately. An unpinned install picks up whatever
released today, and a new default rule turns into a red build on a commit that
changed nothing. If you bump it, bump `uv.lock` and the workflow together.

## Rules — all repos in this account

Standing decisions. Not defaults to weigh — they hold until the user changes them.

**Decide, don't ask.** Pick the best option and proceed; branch locally and work
there. State the choice and the assumption in your report. Stop and ask **only**
for: deleting a repo, branch, or file; anything destroying history or uncommitted
work; irreversible external disclosure. When creating a remote, default private.

**Never destroy.** Archive or unpin, never delete. No force-push to a shared
branch, no `reset --hard` over uncommitted work, no rewriting published history.
Treat the `pgdata` volume as production-like: `docker compose down -v` and manual
`DROP`/`TRUNCATE` need explicit user confirmation.

**Commit identity** is `bilawalaziz` /
`23324237+bilawalaziz@users.noreply.github.com`, set **per-repo, never
`--global`**. **Never write a `Co-Authored-By: Claude` trailer** — 74 such commits
were stripped across four repos on 2026-07-28 and all four force-pushed; merged
PRs still point at dead SHAs.

**Commit early, and keep every commit green.** Commit as soon as a coherent unit
works. Green at *every* point on the branch, not by its end — never commit a
broken intermediate to fix in the next commit. Lint and tests before **each**
commit, not before the PR. A message describing work the code doesn't do yet is a
broken commit even if tests pass. If tests fail, say so with the output; never
report an unfinished step as done.

**Diverge, never overwrite.** Any chance of mismatch → branch off and continue
there. Never resolve a conflict by discarding the other side. Suspect drift →
diff local against remote first; **local is the source of truth** on this machine.
Keep the divergent branch and report what diverged.

**PR flow.** One PR per repo, never straight to `main`. **Merge commits, not
squash**, so the split history survives. Merge this repo **before** the portfolio
page describing it — the site documents what the code contains. Branch off `main`
after the previous merge, never a stale base.

**If a page claims more than the code does, build it** — don't strip the claim.
Genuinely unbuilt work goes in an explicit "Planned" section plus a tracked task.

**Never print, log, or commit the contents of any `.env*` file.**

**Untracked scratch files** in the working tree (`runit.py`,
`publish_different_slots.sh`, …) are the user's own work. Leave them; never commit
them.

**`.gitignore` ignores `*.md` and opts specific files back in** with `!README.md`
and `!CLAUDE.md`. That is deliberate — the user keeps scratch notes as markdown
(`error.md`, `PROJECT_STATUS.md`, …) and they must stay out. If you add a real doc
that belongs in the repo, add a matching `!` line rather than reaching for
`git add -f`, which commits the file but leaves it invisible to `git status`
afterwards.
