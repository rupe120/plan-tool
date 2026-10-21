#!/usr/bin/env python3
"""Structural lint for an IPPT ticket description (docs/TRACKING.md "Ticket contents").

Exit 0: no errors. Exit 1: at least one error. Exit 2: could not run (no `twg`, or the file
or ticket could not be read).

A line that starts with bold text is read as a section header, so keep other bold text
mid-line. Fenced code blocks are not supported; the lint warns when it sees one.

Deliberately not checked, because a machine cannot see them: whether the claims are
true, whether the tier fits, whether an open question remains, whether the brief is
good. Those stay with the author and the reviewer.
"""

import argparse
import json
import re
import subprocess
import sys

TIERS = ("beginner", "experienced", "architect")
ISSUE_TYPE_SHAPED_LABELS = ("bug", "story", "task", "epic", "subtask")
COMMON = ("Summary", "Change", "Out of scope", "Stop / defer")
BEGINNER_BULLETS = ("Start here", "Precedent", "Settled decisions", "Done when", "Reviewer")
OPTIONAL_NON_BEGINNER = ("Precedent",)
WORD_LIMIT = 300
WORD_LIMIT_WITH_EXAMPLE = 500
ATTRIBUTION = re.compile(r"co-authored-by|generated with|\U0001F916", re.IGNORECASE)
TOP = re.compile(r"^\*\*([^*]+?)\*\*(.*)$")
BULLET = re.compile(r"^\s*[*-]\s+\*\*([^*]+?)\*\*(.*)$")
SOURCE = re.compile(r'^Source: (?:BACKLOG #\d+|BUG_BACKLOG "(.+)")$')
ROUTE = re.compile(r"^Route: (plan|direct) — \S.*$")
SEED = re.compile(
    r"^Seed: `plan-seeds/([^`/]+)\.md`"
    r"(?: — authored here; `create` archives it under `plan-seeds/archive/` as "
    r"`([^`/]+)\.replaced\[\.N\]\.md`)?$"
)
PLAN = re.compile(r"^Plan: `docs/implementation-plans/[^`/]+\.md`$")
METADATA_PREFIXES = ("Source:", "Route:", "Seed:", "Plan:")


def adf_to_md(node):
    if isinstance(node, list):
        return "".join(adf_to_md(n) for n in node)
    kind = node.get("type")
    if kind == "text":
        text = node.get("text", "")
        marks = {m["type"] for m in node.get("marks", [])}
        if "code" in marks:
            text = f"`{text}`"
        if "strong" in marks:
            text = f"**{text}**"
        return text
    if kind == "hardBreak":
        return "\n"
    inner = adf_to_md(node.get("content", []))
    if kind in ("paragraph", "heading"):
        return inner + "\n"
    if kind == "codeBlock":
        return f"```\n{inner}\n```\n"
    if kind == "listItem":
        return "* " + inner
    return inner


def label_of(raw):
    return raw.strip().rstrip(":").strip()


def lint(body, tier, title):
    errors, warns = [], []
    lines = [ln.rstrip() for ln in body.replace("\r\n", "\n").split("\n")]
    tops = [
        (i, label_of(m.group(1)), m.group(2)) for i, ln in enumerate(lines) if (m := TOP.match(ln))
    ]
    labels = [t[1] for t in tops]
    required = (
        COMMON
        + (("Where to start",) if tier == "beginner" else ("Done when",))
        + ("Why this tier",)
    )
    allowed = required + (() if tier == "beginner" else OPTIONAL_NON_BEGINNER) + ("Example",)

    for name in required:
        if name not in labels:
            errors.append(f'missing section "{name}"')
    for name in dict.fromkeys(labels):
        if labels.count(name) > 1:
            errors.append(f'section "{name}" appears {labels.count(name)} times')
        if name not in allowed:
            warns.append(f'unexpected section "{name}" for a {tier} ticket')
    present = [n for n in required if n in labels]
    seen = list(dict.fromkeys(n for n in labels if n in required))
    if seen != present:
        errors.append(f"sections out of order: found {seen}, expected {present}")
    if labels and labels[-1] != "Why this tier":
        errors.append('"Why this tier" is not the last section')

    for k, (i, name, rest) in enumerate(tops):
        end = tops[k + 1][0] if k + 1 < len(tops) else len(lines)
        body_lines = [
            ln for ln in lines[i + 1 : end] if not ln.startswith(METADATA_PREFIXES)
        ]
        content = (rest + "\n" + "\n".join(body_lines)).strip()
        if (name in required or name == "Example") and not content:
            errors.append(f'section "{name}" is empty; write "none" if there is nothing to say')

    sources = [i for i, ln in enumerate(lines) if ln.startswith("Source:")]
    if len(sources) != 1:
        errors.append(f'expected exactly one "Source:" line, found {len(sources)}')
    else:
        m = SOURCE.match(lines[sources[0]])
        if not m:
            errors.append(
                '"Source:" line is not `Source: BACKLOG #N` or `Source: BUG_BACKLOG "<heading>"`'
            )
        elif m.group(1) is not None and title is not None and m.group(1) != title:
            errors.append('"Source:" quotes a heading that differs from the ticket title')
        by_label = {n: i for i, n, _ in tops}
        if (
            "Summary" in by_label
            and "Change" in by_label
            and not by_label["Summary"] < sources[0] < by_label["Change"]
        ):
            errors.append('"Source:" must sit between the Summary and Change sections')

    routes = [i for i, ln in enumerate(lines) if ln.startswith("Route:")]
    seeds = [i for i, ln in enumerate(lines) if ln.startswith("Seed:")]
    plans = [i for i, ln in enumerate(lines) if ln.startswith("Plan:")]
    if len(routes) != 1:
        errors.append(f'expected exactly one "Route:" line, found {len(routes)}')
    else:
        m = ROUTE.match(lines[routes[0]])
        if not m:
            errors.append(
                '"Route:" line is not `Route: plan — <starting command>` or '
                '`Route: direct — <one line>`'
            )
        else:
            route_value = m.group(1)
            by_label = {n: i for i, n, _ in tops}
            if (
                "Summary" in by_label
                and "Change" in by_label
                and not by_label["Summary"] < routes[0] < by_label["Change"]
            ):
                errors.append('"Route:" must sit between the Summary and Change sections')
            if route_value == "plan":
                if len(seeds) != 1:
                    errors.append(
                        f'route is "plan" but found {len(seeds)} "Seed:" lines, expected 1'
                    )
                elif not (seed_m := SEED.match(lines[seeds[0]])):
                    errors.append(
                        '"Seed:" line is not `` Seed: `plan-seeds/<name>.md` `` optionally '
                        "followed by the archive clause"
                    )
                else:
                    if seed_m.group(2) is None:
                        warns.append(
                            '"Seed:" has no archive clause: `create` archives the seed, so add '
                            "` — authored here; `create` archives it under `plan-seeds/archive/` "
                            "as `<name>.replaced[.N].md``"
                        )
                    elif seed_m.group(2) != seed_m.group(1):
                        errors.append('"Seed:" archive clause names a different seed than its path')
                    if seeds[0] != routes[0] + 1:
                        errors.append('"Seed:" must sit immediately after the "Route:" line')
                    if len(plans) > 1:
                        errors.append(f'expected at most one "Plan:" line, found {len(plans)}')
                    elif plans and not PLAN.match(lines[plans[0]]):
                        errors.append(
                            '"Plan:" line is not `` Plan: `docs/implementation-plans/<name>.md` ``'
                        )
                    elif plans and plans[0] != seeds[0] + 1:
                        errors.append('"Plan:" must sit immediately after the "Seed:" line')
            elif seeds:
                errors.append('route is "direct" but a "Seed:" line is present')
            elif plans:
                errors.append('route is "direct" but a "Plan:" line is present')

    if tier == "beginner" and "Where to start" in labels:
        k = labels.index("Where to start")
        end = tops[k + 1][0] if k + 1 < len(tops) else len(lines)
        found = []
        for ln in lines[tops[k][0] + 1 : end]:
            if m := BULLET.match(ln):
                found.append([label_of(m.group(1)), m.group(2).strip()])
            elif found and ln.strip():
                found[-1][1] = f"{found[-1][1]} {ln.strip()}".strip()
        positions = []
        for want in BEGINNER_BULLETS:
            hit = next((j for j, (lab, _) in enumerate(found) if lab.startswith(want)), None)
            if hit is None:
                errors.append(f'"Where to start" is missing the "{want}" bullet')
            else:
                positions.append(hit)
                if not found[hit][1]:
                    errors.append(
                        f'"{want}" bullet is empty; write "none" if there is nothing to say'
                    )
        if positions != sorted(positions):
            errors.append('"Where to start" bullets are out of order')
    elif tier != "beginner" and "Where to start" in labels:
        warns.append('"Where to start" is for beginner tickets only')

    if "Example" in labels:
        by_label = {n: i for i, n, _ in tops}
        if "Summary" in by_label and "Change" in by_label and not (
            by_label["Summary"] < by_label["Example"] < by_label["Change"]
        ):
            errors.append('"Example" must sit between the Summary and Change sections')
    else:
        warns.append(
            'no "Example" section: add a worked example that follows one real input through '
            "the change (what is run, what the code reads, what is printed or refused)"
        )

    words = len(body.split())
    limit = WORD_LIMIT_WITH_EXAMPLE if "Example" in labels else WORD_LIMIT
    if words > limit:
        warns.append(
            f"{words} words; over {limit} only when a long list of sites justifies it"
        )
    if re.search(r"^\s*(```|~~~)", body, re.MULTILINE):
        warns.append(
            "fenced code block: a bold-led line inside one is still read as a section header"
        )
    if ATTRIBUTION.search(body):
        errors.append("attribution trailer or footer in the ticket text")
    return words, errors, warns


def load_live(key):
    try:
        out = subprocess.run(
            ["twg", "jira", "workitem", "get", key], capture_output=True, text=True
        )
    except FileNotFoundError:
        print("error: `twg` is not on PATH", file=sys.stderr)
        return None
    if out.returncode:
        try:
            reason = json.loads(out.stdout)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            reason = (out.stderr or out.stdout).strip()
        print(f"error: reading {key} failed: {reason}", file=sys.stderr)
        return None
    try:
        data = json.loads(out.stdout)
        item = data[0] if isinstance(data, list) else data
    except (ValueError, IndexError):
        print(f"error: reading {key} did not return JSON", file=sys.stderr)
        return None
    if not isinstance(item, dict) or "key" not in item:
        print(f"error: reading {key} did not return a ticket", file=sys.stderr)
        return None
    fields = item.get("fields", item)
    description = fields.get("description")
    body = description if isinstance(description, str) else adf_to_md(description or {})
    kind, priority, status = (
        (fields.get(f) or {}).get("name") for f in ("issuetype", "priority", "status")
    )
    print(f"{key}: {kind} / {priority} / {status} / labels {fields.get('labels', [])}")
    return body, fields.get("labels", []), fields.get("summary", "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "file", nargs="?", help="description markdown, body only: exactly what is sent to Jira"
    )
    ap.add_argument("--jira", metavar="KEY", help="lint the live ticket instead of a file")
    ap.add_argument(
        "--tier", choices=TIERS, help="required with a file; a live ticket's tier label is used"
    )
    ap.add_argument(
        "--title", help="the ticket title, to compare with the Source: line (files only)"
    )
    args = ap.parse_args(argv)
    if bool(args.file) == bool(args.jira):
        ap.error("give a file or --jira KEY, not both")

    if args.jira:
        live = load_live(args.jira)
        if live is None:
            return 2
        body, labels, title = live
        tiers = [lab for lab in labels if lab in TIERS]
        if len(tiers) != 1:
            print(f"{args.jira}: error: expected exactly one tier label, found {tiers or 'none'}")
            return 1
        tier = tiers[0]
        for lab in labels:
            if lab.lower() in ISSUE_TYPE_SHAPED_LABELS:
                print(
                    f"{args.jira}: warn: label '{lab}' names an issue type, already carried by "
                    "the type field; docs/TRACKING.md's label table has no such label — check "
                    "it isn't a stray label from a ticket authored outside the jira-ticket skill"
                )
    else:
        if not args.tier:
            ap.error("--tier is required with a file")
        try:
            with open(args.file, encoding="utf-8") as fh:
                body = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: reading {args.file} failed: {exc}", file=sys.stderr)
            return 2
        tier, title = args.tier, args.title

    words, errors, warns = lint(body, tier, title)
    name = args.jira or args.file
    for e in errors:
        print(f"{name}: error: {e}")
    for w in warns:
        print(f"{name}: warn: {w}")
    print(f"{name}: {tier}, {words} words, {len(errors)} errors, {len(warns)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
