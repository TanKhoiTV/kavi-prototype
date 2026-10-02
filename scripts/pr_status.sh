#!/usr/bin/env bash
#
# pr_status.sh — pull-request dashboard: review inbox + author outbox.
#
# Answers, in one command, the two questions that matter after a few days away:
#   1. Which open PRs are waiting on MY review?           (inbox)
#   2. Which of MY open PRs are reviewed, and which are stalled? (outbox)
#
# The inbox deliberately does NOT rely on GitHub reviewer assignment alone.
# PRs in this repo are frequently opened without a reviewer requested, so an
# unassigned PR authored by someone else still counts as awaiting your review.
# Relying on `--review-requested` alone silently reports "nothing to review"
# while PRs sit unreviewed. See `AGENTS.md` -> "PR review status".
#
# Drafts are listed, never hidden — they are marked DRAFT and counted
# separately, because a draft is often "nearly ready" rather than "ignore".
#
# Usage:
#   scripts/pr_status.sh
#   PR_STATUS_STALE_DAYS=7 scripts/pr_status.sh
#   PR_STATUS_REPO=owner/name scripts/pr_status.sh
#   scripts/pr_status.sh --web      # open the review inbox in a browser
#
# Environment:
#   PR_STATUS_REPO         default: the current repository
#   PR_STATUS_STALE_DAYS   idle days before flagging STALE (default 3)
#   PR_STATUS_LIMIT        max open PRs to fetch (default 200)
#
# Requires: gh, authenticated (`gh auth status`). No jq needed — this uses
# gh's built-in --jq.
#
set -euo pipefail

REPO="${PR_STATUS_REPO:-}"
STALE_DAYS="${PR_STATUS_STALE_DAYS:-3}"
LIMIT="${PR_STATUS_LIMIT:-200}"

command -v gh >/dev/null 2>&1 || {
	printf 'error: gh CLI not found (https://cli.github.com)\n' >&2
	exit 127
}

if ! gh auth status >/dev/null 2>&1; then
	printf 'error: gh is not authenticated — run: gh auth login\n' >&2
	exit 1
fi

[[ "$STALE_DAYS" =~ ^[0-9]+$ ]] || {
	printf 'error: PR_STATUS_STALE_DAYS must be a non-negative integer\n' >&2
	exit 2
}
[[ "$LIMIT" =~ ^[0-9]+$ ]] || {
	printf 'error: PR_STATUS_LIMIT must be a non-negative integer\n' >&2
	exit 2
}

if [[ -z "$REPO" ]]; then
	REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi

ME="$(gh api user --jq .login)"
[[ "$ME" =~ ^[A-Za-z0-9-]+$ ]] || {
	printf "error: unexpected login '%s'\n" "$ME" >&2
	exit 2
}

# `--web` convenience: GitHub's native review-inbox filter for this repo.
if [[ "${1:-}" == "--web" ]]; then
	gh pr list --repo "$REPO" --state open --search "review-requested:$ME" --web
	exit 0
fi

# The report is built entirely in one jq program (gh's embedded jq), because a
# standalone jq binary is not guaranteed on PATH. @ME@, @STALE@, and @LIMIT@
# are substituted below; all are validated above so interpolation is safe.
PROG=$(
	cat <<'JQ'
# ── formatting helpers ───────────────────────────────────────────────────────
def pad($n): if length >= $n then . else . + (" " * ($n - length)) end;
def cut($n): if length > $n then .[0:($n - 3)] + "..." else . end;
def dur($d): if $d <= 0 then "today" elif $d == 1 then "1d" else "\($d)d" end;
def days(x): ((now - (x | fromdateiso8601)) / 86400 | floor);
def idle: days(.updatedAt);
def age: days(.createdAt);
def isstale: idle >= @STALE@;

# ── per-PR facts ─────────────────────────────────────────────────────────────
def myrev: [.latestReviews[]? | select(.author.login == "@ME@") | .state];
def approvals:
  [.reviews[]? | select(.author.login != "@ME@")
   | select(.state == "APPROVED" or .state == "CHANGES_REQUESTED")]
  | group_by(.author.login)
  | map(sort_by(.submittedAt) | last | select(.state == "APPROVED"))
  | length;
def revsum:
  ([.latestReviews[]? | select(.author.login != "@ME@") | "\(.author.login):\(.state)"] | join(",")) as $s
  | if $s == "" then "no reviews" else $s end;
def reqdisp:
  ([.reviewRequests[]? | (.login // .name // .slug)]) as $r
  | if ($r | length) == 0 then "UNASSIGNED"
    elif ($r | length) == 1 then "rq:" + $r[0]
    else "rq:" + $r[0] + "+\((($r | length) - 1))"
    end;

# Render one PR as a single aligned row.
def row:
  "   "
  + (("#\(.number)") | pad(7))
  + ((if .isDraft then "DRAFT" else "" end) | pad(7))
  + (reqdisp | cut(20) | pad(21))
  + (((dur(idle)) + " idle") | pad(11))
  + (((dur(age)) + " open") | pad(11))
  + ((if isstale then "STALE" else "" end) | pad(7))
  + ((if (myrev | length) > 0 then "you:" + (myrev | join(",")) else revsum end) | cut(34) | pad(36))
  + .title;

# Section header with an underline sized to the title.
def section($t): "── \($t) " + ("─" * (68 - ($t | length)));

. as $all
| ($all | map(select(.author.login != "@ME@"))) as $foreign
| ($foreign | map(select((myrev | length) == 0))) as $waiting
| (($waiting | map(select(.isDraft)) | length)) as $waiting_draft
| ($foreign | map(select((myrev | length) > 0))) as $handled
| ($all | map(select(.author.login == "@ME@"))) as $mine
| ($mine | map(select(approvals == 0))) as $mine_unreviewed
| ($all | map(select(isstale))) as $stale
# A fetched count below the limit means every open PR was retrieved, so the
# counts are exact and need no qualifier. Only when the fetch hits the limit is
# the set possibly incomplete — then label counts "fetched" and warn.
| (($all | length) >= @LIMIT@) as $trunc
| (if $trunc then " fetched" else "" end) as $fq

| section("WAITING ON YOUR REVIEW (\($waiting | length)\($fq))"),
  (if ($waiting | length) == 0 then
     "   none" + (if $trunc then " among the fetched PRs" else " — no unreviewed open PRs authored by others" end)
   else ($waiting[] | row) end),
  (if $waiting_draft > 0 then
     "   note: \($waiting_draft) of these are DRAFT — may not be ready for review"
   else empty end),
  "",
  section("YOUR OPEN PRS (\($mine | length)\($fq))"),
  (if ($mine | length) == 0 then
     "   " + (if $trunc then "none of the fetched PRs are yours" else "you have no open PRs" end)
   else
     ($mine[] | row) ,
     (if ($mine_unreviewed | length) > 0 then
        "   note: \($mine_unreviewed | length) of yours have no peer approval yet"
      else empty end)
   end),
  "",
  section("ALREADY REVIEWED BY YOU, STILL OPEN (\($handled | length)\($fq))"),
  (if ($handled | length) == 0 then
     "   none"
   else ($handled[] | row) end),
  "",
  section("SUMMARY"),
  "   \($all | length)\($fq) open PRs  ·  \($waiting | length) awaiting you"
  + " (\($waiting_draft) draft)"
  + "  ·  \($mine | length) yours (\($mine_unreviewed | length) unapproved)"
  + "  ·  \($stale | length) idle >= @STALE@d",
  (if $trunc then
     "   warning: only the first @LIMIT@ open PRs were fetched — counts may be incomplete (raise PR_STATUS_LIMIT)"
   else empty end)
JQ
)

PROG="${PROG//@ME@/$ME}"
PROG="${PROG//@STALE@/$STALE_DAYS}"
PROG="${PROG//@LIMIT@/$LIMIT}"

printf 'PR status — %s\n' "$REPO"
printf '%s · as %s · stale >= %sd\n\n' "$(date -u '+%Y-%m-%d %H:%M UTC')" "$ME" "$STALE_DAYS"

gh pr list \
	--repo "$REPO" \
	--state open \
	--limit "$LIMIT" \
	--json number,title,author,isDraft,createdAt,updatedAt,reviewRequests,reviews,latestReviews \
	--jq "$PROG"
