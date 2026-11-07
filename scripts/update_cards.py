#!/usr/bin/env python3
"""Regenerates assets/stats.svg and assets/languages.svg from the GitHub API (through the gh CLI).

The cards are drawn here and served from this repository, so the profile does not depend on
third-party card services. Standard library only. The colours follow the viewer's light/dark theme.
"""
import datetime as dt
import json
import os
import subprocess
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "morizin")
OUT = Path(__file__).resolve().parent.parent / "assets"
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "SCSS", "Makefile", "Dockerfile", "Shell"}
COLORS = {"Python": "#3572A5", "Rust": "#dea584", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "C++": "#f34b7d",
          "Cuda": "#76b900", "C": "#8a8a8a", "Java": "#b07219", "Ruby": "#701516", "Astro": "#ff5a03", "TeX": "#3D6117",
          "Go": "#00ADD8", "Kotlin": "#A97BFF", "Swift": "#F05138"}


def gh(*args):
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def all_repos():
    repos, page = [], 1
    while True:
        chunk = gh(f"users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            return repos
        page += 1


def collect():
    user = gh(f"users/{USER}")
    repos = all_repos()
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    langs = {}
    for r in own:
        if r["size"] == 0 or r["archived"]:
            continue
        for name, n in gh(f"repos/{USER}/{r['name']}/languages").items():
            if name not in SKIP_LANGS:
                langs[name] = langs.get(name, 0) + n
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = ("query($login:String!,$from:DateTime!){user(login:$login){contributionsCollection(from:$from){"
         "totalCommitContributions totalPullRequestContributions totalIssueContributions}}}")
    c = gh("graphql", "-f", f"query={q}", "-F", f"login={USER}", "-f", f"from={since}")["data"]["user"]["contributionsCollection"]
    return {"stars": stars, "commits": c["totalCommitContributions"], "prs": c["totalPullRequestContributions"],
            "issues": c["totalIssueContributions"], "repos": user["public_repos"], "followers": user["followers"], "langs": langs}


STYLE = """<style>
:root{--bg:#ffffff;--fg:#1f2328;--muted:#656d76;--accent:#0969da;--line:#d0d7de}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--accent:#58a6ff;--line:#30363d}}
text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
.bg{fill:var(--bg);stroke:var(--line)}.title{font-size:16px;font-weight:600;fill:var(--accent)}
.label{font-size:12px;fill:var(--muted)}.value{font-size:22px;font-weight:600;fill:var(--fg)}.name{font-size:12px;fill:var(--fg)}.pct{font-size:12px;fill:var(--muted)}
</style>"""


def frame(title, body, w=495, h=205):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">\n'
            f'{STYLE}\n<rect class="bg" x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="8"/>\n'
            f'<text class="title" x="24" y="34">{escape(title)}</text>\n{body}\n</svg>\n')


def stats_card(d):
    cells = [("Stars earned", d["stars"]), ("Commits, last 12 months", d["commits"]), ("Pull requests, last 12 months", d["prs"]),
             ("Public repositories", d["repos"]), ("Followers", d["followers"]), ("Issues, last 12 months", d["issues"])]
    out = []
    for i, (label, value) in enumerate(cells):
        x, y = 24 + (i // 3) * 236, 70 + (i % 3) * 44      # y = label baseline; the value sits 24px below it
        out.append(f'<text class="label" x="{x}" y="{y}">{escape(label)}</text>'
                   f'<text class="value" x="{x}" y="{y + 24}">{value:,}</text>')
    return frame(f"GitHub stats: {USER}", "\n".join(out))


def languages_card(langs):
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:6]
    total = sum(n for _, n in top) or 1
    bar, x = [], 24.0
    for name, n in top:
        w = 447 * n / total
        bar.append(f'<rect x="{x:.1f}" y="52" width="{max(w, 1):.1f}" height="10" fill="{COLORS.get(name, "#8b949e")}"/>')
        x += w
    legend = []
    for i, (name, n) in enumerate(top):
        cx, cy = 24 + (i % 2) * 236, 96 + (i // 2) * 30
        legend.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{COLORS.get(name, "#8b949e")}"/>'
                      f'<text class="name" x="{cx + 18}" y="{cy}">{escape(name)}</text>'
                      f'<text class="pct" x="{cx + 150}" y="{cy}">{100 * n / total:.1f}%</text>')
    clip = '<clipPath id="r"><rect x="24" y="52" width="447" height="10" rx="5"/></clipPath>'
    return frame("Top languages (notebooks excluded)", f'{clip}<g clip-path="url(#r)">{"".join(bar)}</g>\n' + "\n".join(legend))


if __name__ == "__main__":
    data = collect()
    OUT.mkdir(exist_ok=True)
    (OUT / "stats.svg").write_text(stats_card(data))
    (OUT / "languages.svg").write_text(languages_card(data["langs"]))
    print(json.dumps({k: v for k, v in data.items() if k != "langs"}), "| top languages:",
          sorted(data["langs"], key=data["langs"].get, reverse=True)[:6])
