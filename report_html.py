"""HTML audit report, SPEC-8's 6-page layout. Plain string building, no
template engine — same convention as GeoMonitor's dashboard.py. Visual system
(CSS tokens, components) ported wholesale from the approved mockup at
the-audit-mockup.html; this file makes it data-driven instead of hardcoded.

Renders honestly: a field the pipeline doesn't compute shows a "pending" /
"not scored yet" state rather than a fabricated number. See PENDING NOTES
below for what's still genuinely missing and why.

PENDING NOTES (real gaps, not just missing data for this one run):
- "Cited" (linked, not just named) isn't tracked anywhere in aiquery.py —
  only `mentioned` exists. The named/cited split from the mockup is dropped
  to mention-only until a citation extractor exists.
- Sentiment classification doesn't exist in GeoAudit at all (that's
  GeoMonitor's extract.py, a different repo/pipeline) — always pending here.
- Structured-data field checks only cover schema type + name + phone
  (checks.check_schema's actual granularity) — address/hours/service
  description aren't checked by checks.py yet, so those rows are omitted
  rather than invented.
- Citation-domain ("where citations point") needs a citation extractor that
  doesn't exist yet — always pending.
- Competitor "shows up for" / niche notes (mockup's hardcoded text) can't be
  derived generically from score_competitors()'s {mentioned, total} shape —
  dropped from the table.
"""
import html as _html

import checks as checks_module

_CSS = """
  :root{
    --ink:#1a2332; --ink-soft:#4d5b6b;
    --accent:#0e6e6e; --accent-soft:#eef4f4; --accent-line:#bfd6d6;
    --warn:#8a2c2c; --warn-soft:#f9eeee; --warn-line:#e4c6c6;
    --good:#2f7d4f; --good-soft:#eaf4ee; --good-line:#c3ddcd;
    --pending:#8a6d1f; --pending-soft:#faf3e2; --pending-line:#e6d5a8;
    --gray:#6b7684; --rule:#d7e0e0;
    --bg:#f7fafa; --surface:#ffffff; --surface-2:#fbfdfd;
    --font-display:'Fraunces', Georgia, 'Times New Roman', serif;
    --font-body:'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-mono:'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
    padding-top:env(safe-area-inset-top,0px);
    padding-bottom:env(safe-area-inset-bottom,0px);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --ink:#e7edf0; --ink-soft:#aab6c2;
      --accent:#3fc2bb; --accent-soft:#122324; --accent-line:#245050;
      --warn:#e59a9a; --warn-soft:#2a1616; --warn-line:#5a2c2c;
      --good:#8fd2a8; --good-soft:#122a1c; --good-line:#2c5a3e;
      --pending:#e8c877; --pending-soft:#2a230f; --pending-line:#5a4a24;
      --gray:#8a95a3; --rule:#2a3540;
      --bg:#0d1216; --surface:#131a20; --surface-2:#10161b;
    }
  }
  :root[data-theme="dark"]{
    --ink:#e7edf0; --ink-soft:#aab6c2;
    --accent:#3fc2bb; --accent-soft:#122324; --accent-line:#245050;
    --warn:#e59a9a; --warn-soft:#2a1616; --warn-line:#5a2c2c;
    --good:#8fd2a8; --good-soft:#122a1c; --good-line:#2c5a3e;
    --pending:#e8c877; --pending-soft:#2a230f; --pending-line:#5a4a24;
    --gray:#8a95a3; --rule:#2a3540;
    --bg:#0d1216; --surface:#131a20; --surface-2:#10161b;
  }
  *{box-sizing:border-box;}
  [hidden]{display:none!important;}
  img{max-width:100%;}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:var(--font-body); font-size:15px; line-height:1.55;
    padding-inline:0;
  }
  .shell{
    display:grid; grid-template-columns:220px 1fr;
    max-width:1180px; margin:0 auto;
  }
  .masthead{
    grid-column:1 / -1;
    display:flex; align-items:baseline; justify-content:space-between;
    gap:16px; flex-wrap:wrap;
    padding:28px 24px 20px;
    border-bottom:1px solid var(--rule);
  }
  .masthead .brand{
    font-family:var(--font-mono); font-size:11px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--gray);
  }
  .masthead h1{
    font-family:var(--font-display); font-weight:600; font-size:clamp(28px,4vw,38px);
    margin:2px 0 0; text-wrap:balance; letter-spacing:-.01em;
  }
  .masthead .meta{
    text-align:right; font-family:var(--font-mono); font-size:12px; color:var(--gray);
    line-height:1.7;
  }
  .masthead .meta b{color:var(--ink); font-weight:600;}
  .badge-sample{
    display:inline-block; margin-top:6px; padding:3px 9px;
    background:var(--pending-soft); color:var(--pending); border:1px solid var(--pending-line);
    border-radius:3px; font-family:var(--font-mono); font-size:10.5px;
    letter-spacing:.08em; text-transform:uppercase;
  }
  nav.toc{
    padding:24px 12px 40px; position:sticky; top:calc(env(safe-area-inset-top,0px) + 16px);
    align-self:start; height:max-content;
  }
  nav.toc a{
    display:flex; gap:10px; align-items:baseline;
    padding:9px 12px; border-radius:6px; text-decoration:none;
    color:var(--ink-soft); font-size:13.5px; font-weight:500;
  }
  nav.toc a:hover{background:var(--surface-2);}
  nav.toc a.active{background:var(--accent-soft); color:var(--accent);}
  nav.toc .n{font-family:var(--font-mono); font-size:11px; color:var(--gray); min-width:14px;}
  nav.toc a.active .n{color:var(--accent);}
  main{padding:8px 24px 80px; min-width:0;}
  section.page{padding:44px 0; border-bottom:1px solid var(--rule);}
  section.page:last-of-type{border-bottom:none;}
  .eyebrow{
    font-family:var(--font-mono); font-size:11px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--accent); margin:0 0 8px;
  }
  h2{
    font-family:var(--font-display); font-weight:600; font-size:clamp(22px,3vw,28px);
    margin:0 0 6px; text-wrap:balance;
  }
  .dek{color:var(--gray); font-size:14.5px; max-width:62ch; margin:0 0 28px;}
  p{max-width:66ch;}
  .lede{
    font-family:var(--font-display); font-size:19px; font-weight:500;
    color:var(--ink); max-width:52ch; line-height:1.45; margin:0 0 28px;
  }
  .score-row{display:flex; gap:16px; flex-wrap:wrap; margin-bottom:8px;}
  .score-card{
    flex:1 1 220px; background:var(--surface); border:1px solid var(--rule);
    border-radius:10px; padding:18px 18px 16px; position:relative;
  }
  .score-card .label{
    font-family:var(--font-mono); font-size:11px; letter-spacing:.06em;
    text-transform:uppercase; color:var(--gray); margin-bottom:10px;
  }
  .score-card .value{
    font-family:var(--font-display); font-size:34px; font-weight:600;
    font-variant-numeric:tabular-nums; line-height:1;
  }
  .score-card .sub{font-size:12.5px; color:var(--gray); margin-top:8px;}
  .pill{
    display:inline-flex; align-items:center; gap:6px;
    font-family:var(--font-mono); font-size:11px; letter-spacing:.04em;
    padding:3px 9px; border-radius:20px; font-weight:600;
  }
  .pill.pending{background:var(--pending-soft); color:var(--pending); border:1px solid var(--pending-line);}
  .pill.warn{background:var(--warn-soft); color:var(--warn); border:1px solid var(--warn-line);}
  .pill.good{background:var(--good-soft); color:var(--good); border:1px solid var(--good-line);}
  .pill .dot{width:6px; height:6px; border-radius:50%; background:currentColor;}
  .no-composite{
    margin-top:20px; padding:14px 16px; background:var(--surface-2);
    border:1px dashed var(--rule); border-radius:8px;
    font-size:13px; color:var(--gray);
  }
  .no-composite b{color:var(--ink-soft);}
  .subhead{
    font-family:var(--font-mono); font-size:11px; letter-spacing:.08em;
    text-transform:uppercase; color:var(--gray); margin:36px 0 14px;
  }
  .breakdown-grid{display:grid; grid-template-columns:1fr 1fr; gap:16px;}
  .breakdown-card{background:var(--surface); border:1px solid var(--rule); border-radius:10px; padding:18px 20px;}
  .breakdown-card h4{margin:0 0 4px; font-size:13.5px; font-weight:600;}
  .breakdown-card .note{font-size:12px; color:var(--gray); margin:0 0 14px;}
  .bar-row{display:grid; grid-template-columns:108px 1fr 52px; align-items:center; gap:10px; margin-bottom:10px;}
  .bar-row:last-child{margin-bottom:0;}
  .bar-row .bl{font-size:12.5px; color:var(--ink-soft);}
  .bar-track{height:8px; background:var(--surface-2); border:1px solid var(--rule); border-radius:5px; overflow:hidden;}
  .bar-fill{height:100%; background:var(--accent); border-radius:5px 0 0 5px;}
  .bar-fill.pending{background:repeating-linear-gradient(135deg,var(--rule),var(--rule) 5px,transparent 5px,transparent 10px);}
  .bar-row .bv{font-family:var(--font-mono); font-size:12px; text-align:right; font-variant-numeric:tabular-nums; color:var(--ink-soft);}
  .bar-row .bv.real{color:var(--ink); font-weight:600;}
  .pending-block{
    background:var(--surface-2); border:1px dashed var(--rule); border-radius:10px;
    padding:16px 18px; font-size:13px; color:var(--gray);
  }
  .pending-block b{color:var(--ink-soft); display:block; font-size:13.5px; margin-bottom:4px;}
  @media (max-width:640px){ .breakdown-grid{grid-template-columns:1fr;} .bar-row{grid-template-columns:88px 1fr 44px;} }
  ol.findings{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:14px;}
  ol.findings li{
    display:grid; grid-template-columns:34px 1fr; gap:14px;
    background:var(--surface); border:1px solid var(--rule); border-radius:10px;
    padding:16px 18px;
  }
  ol.findings .rank{font-family:var(--font-display); font-size:20px; font-weight:600; color:var(--rule);}
  ol.findings li.sev-high .rank{color:var(--warn);}
  ol.findings h3{margin:0 0 4px; font-size:15px; font-weight:600;}
  ol.findings p{margin:0; font-size:13.5px; color:var(--ink-soft);}
  .tbl-wrap{overflow-x:auto; border:1px solid var(--rule); border-radius:10px;}
  table{width:100%; border-collapse:collapse; font-size:13.5px; min-width:520px;}
  thead th{
    text-align:left; font-family:var(--font-mono); font-size:10.5px;
    letter-spacing:.08em; text-transform:uppercase; color:var(--gray);
    padding:12px 16px; background:var(--surface-2); border-bottom:1px solid var(--rule);
  }
  tbody td{padding:12px 16px; border-bottom:1px solid var(--rule);}
  tbody tr:last-child td{border-bottom:none;}
  tbody tr:hover{background:var(--surface-2);}
  td.name{font-weight:600;}
  td.note{color:var(--gray);}
  ul.actions{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:12px;}
  ul.actions li{
    display:flex; gap:12px; align-items:flex-start;
    background:var(--surface); border:1px solid var(--rule); border-radius:10px; padding:14px 16px;
  }
  ul.actions .tag{
    flex:none; font-family:var(--font-mono); font-size:10px; letter-spacing:.06em;
    text-transform:uppercase; padding:3px 8px; border-radius:4px; margin-top:2px;
  }
  ul.actions .tag.diy{background:var(--good-soft); color:var(--good); border:1px solid var(--good-line);}
  ul.actions .tag.us{background:var(--accent-soft); color:var(--accent); border:1px solid var(--accent-line);}
  ul.actions strong{display:block; font-size:14px; margin-bottom:2px;}
  ul.actions span.desc{font-size:13px; color:var(--ink-soft);}
  .limit-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px;}
  .limit-card{background:var(--surface); border:1px solid var(--rule); border-radius:10px; padding:16px 18px;}
  .limit-card h3{margin:0 0 6px; font-size:14px;}
  .limit-card p{margin:0; font-size:13px; color:var(--ink-soft);}
  .argument{
    margin-top:24px; padding:18px 20px; background:var(--accent-soft);
    border:1px solid var(--accent-line); border-radius:10px;
    font-family:var(--font-display); font-size:16px; color:var(--ink);
  }
  .compare{display:grid; grid-template-columns:1fr 1fr; gap:16px;}
  .compare .col{background:var(--surface); border:1px solid var(--rule); border-radius:10px; padding:18px 20px;}
  .compare .col.now{opacity:.75;}
  .compare .col.sub{border-color:var(--accent-line); background:var(--accent-soft);}
  .compare h3{margin:0 0 12px; font-size:14px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:.06em;}
  .compare ul{margin:0; padding-left:18px; font-size:13.5px; color:var(--ink-soft); display:flex; flex-direction:column; gap:8px;}
  .compare .col.sub ul{color:var(--ink);}
  footer.doc{
    grid-column:1/-1; padding:24px; text-align:center;
    font-family:var(--font-mono); font-size:11px; color:var(--gray);
  }
  @media (max-width: 760px){
    .shell{grid-template-columns:1fr;}
    nav.toc{position:static; display:flex; overflow-x:auto; gap:4px; padding:14px 16px; border-bottom:1px solid var(--rule);}
    nav.toc a{white-space:nowrap; padding:8px 12px;}
    .masthead{padding:22px 16px 16px;}
    .masthead .meta{text-align:left;}
    main{padding:8px 16px 60px;}
    .compare{grid-template-columns:1fr;}
  }
"""

# Which of the 23 prompts.toml labels are discovery / brand / competitive.
# Kept in sync with prompts.toml by hand — there's no shared source of truth
# for this grouping yet (prompts.toml doesn't tag category, only label text).
_DISCOVERY_LABELS = {
    "Recommendation", "Emergency / near-me", "Comparison", "Problem-first",
    "Niche: best of specialty", "Niche: specific service", "Niche: creative/fine art",
    "Workshops: specialty", "Workshops: general", "Event: corporate",
    "Event: conference/TEDx", "Award-winning",
}
_BRAND_LABELS = {
    "Brand: what is", "Vetting", "Brand: reviews", "Brand: pricing",
    "Brand: who is behind it", "Brand: press/media",
}
_COMPETITIVE_LABELS = {
    "Competitive: vs others", "Competitive: alternatives", "Competitive: specialty compare",
    "Competitive: which to choose", "Competitive: companies compared",
}


def _esc(text):
    return _html.escape(str(text)) if text is not None else ""


def _pct(n, d):
    return round(100 * n / d) if d else 0


def _pending_score_card(label):
    return f"""<div class="score-card">
      <div class="label">{_esc(label)}</div>
      <div class="value" style="color:var(--pending); font-size:22px;">Pending</div>
      <span class="pill pending"><span class="dot"></span>not run yet</span>
      <div class="sub">Waiting on the audit run for this check.</div>
    </div>"""


def _score_card(label, value, kind, pill_text, sub):
    return f"""<div class="score-card">
      <div class="label">{_esc(label)}</div>
      <div class="value" style="color:var(--{kind}); font-size:22px;">{_esc(value)}</div>
      <span class="pill {kind}"><span class="dot"></span>{_esc(pill_text)}</span>
      <div class="sub">{_esc(sub)}</div>
    </div>"""


def _channel_score_card(label, value, weight, sub):
    if value is None:
        return _pending_score_card(f"{label} ({weight}%)")
    kind = "good" if value < 50 else "warn"
    return _score_card(f"{label} ({weight}%)", round(value), kind, "risk score", sub)


def _composite_score_block(score):
    """SPEC-3's Digital Invisibility Risk Score (0-100, lower is better).
    Weights ported from SCORE-BUILDER.html — see scoring.py's docstring.
    Google/Local/Brand are 0-3 human-judgment inputs in the source tool, not
    automated; they render as "pending" until someone passes --position
    --indexed --bing etc. on the CLI."""
    if not score:
        return """<div class="no-composite"><b>No score computed.</b> Run the audit through audit.py to get one.</div>"""
    w = score["weights"]
    total = score["composite"]
    total_html = (f'<div class="value" style="font-size:44px;">{round(total)}</div>'
                  f'<div class="sub">Composite risk score &mdash; 0 is invisible-risk-free, 100 is worst.</div>') \
        if total is not None else \
        '<div class="value" style="color:var(--pending); font-size:22px;">Not enough scored</div>'
    return f"""<div class="score-card" style="flex:1 1 100%; margin-bottom:16px;">
      <div class="label">The score (SPEC-3 weights &mdash; found in a design mockup, not officially locked)</div>
      {total_html}
    </div>
    <div class="score-row">
      {_channel_score_card("AI assistants", score["ai"], w["ai"], "Automated from this run's 23-prompt data")}
      {_channel_score_card("Search engines", score["google"], w["google"], "Needs --position --indexed --bing (0-3 each)")}
      {_channel_score_card("Local and maps", score["local"], w["local"], "Needs --pack --gbp --apple --nap (0-3 each)")}
      {_channel_score_card("What AI says", score["brand"], w["brand"], "Needs --acc (0-3)")}
    </div>"""


def _crawler_card(checks_results):
    c = (checks_results or {}).get("crawler")
    if not c or c.get("passed") is None:
        return _pending_score_card("Crawler access")
    if c["passed"]:
        return _score_card("Crawler access", "Clear", "good", "no agents blocked", c["finding"])
    return _score_card("Crawler access", "Blocked", "warn", "agents blocked", c["finding"])


def _schema_card(checks_results):
    c = (checks_results or {}).get("schema")
    if not c or c.get("passed") is None:
        return _pending_score_card("Structured data")
    if c["passed"]:
        return _score_card("Structured data", "OK", "good", "LocalBusiness present", c["finding"])
    return _score_card("Structured data", "Issue", "warn", "needs fixing", c["finding"])


def _mention_rate_card(aiquery_results, business):
    if not aiquery_results:
        return _pending_score_card("AI mention rate")
    total = len(aiquery_results)
    named = sum(1 for r in aiquery_results if r.get("mentioned"))
    pct = _pct(named, total)
    kind = "good" if pct >= 50 else "warn"
    return _score_card("AI mention rate", f"{pct}%", kind, f"{named} of {total} prompts",
                        f"{business} named in {named}/{total} answers this pass.")


def _bar(label, value_text, width_pct, pending=False, real=True):
    fill_cls = "bar-fill pending" if pending else "bar-fill"
    width = 100 if pending else width_pct
    val_cls = "bv real" if (real and not pending) else "bv"
    return (f'<div class="bar-row"><span class="bl">{_esc(label)}</span>'
            f'<div class="bar-track"><div class="{fill_cls}" style="width:{width}%"></div></div>'
            f'<span class="{val_cls}">{_esc(value_text)}</span></div>')


def _named_only_card(aiquery_results):
    if not aiquery_results:
        return ('<div class="breakdown-card"><h4>Named</h4>'
                '<p class="note">Whether the business was named in the answer at all.</p>'
                + _bar("Named", "pending", 0, pending=True) + "</div>")
    total = len(aiquery_results)
    named = sum(1 for r in aiquery_results if r.get("mentioned"))
    body = (f'<div class="breakdown-card"><h4>Named</h4>'
            f'<p class="note">Whether {"the business" if False else "it"} was named in the answer. '
            f'"Cited" (linked, not just named) isn\'t tracked by this pipeline yet — '
            f'no citation extractor exists, so it isn\'t shown as a separate figure rather than guessed at.</p>'
            + _bar("Named", f"{named} / {total}", _pct(named, total)) + "</div>")
    return body


def _by_platform_card(aiquery_results):
    all_engines = ["ChatGPT", "Perplexity", "Gemini", "Claude"]
    rows = []
    if aiquery_results:
        seen = {}
        for r in aiquery_results:
            seen.setdefault(r["engine"], []).append(r)
        for name in all_engines:
            if name in seen:
                cell = seen[name]
                named = sum(1 for r in cell if r.get("mentioned"))
                rows.append(_bar(name, f"{_pct(named, len(cell))}%", _pct(named, len(cell))))
            else:
                rows.append(_bar(name, "pending", 0, pending=True))
    else:
        rows = [_bar(name, "pending", 0, pending=True) for name in all_engines]
    note = ("This pass covers " + ", ".join(sorted({r["engine"] for r in aiquery_results}))
            + ". The rest run once the full audit starts.") if aiquery_results else \
           "No AI-query results yet."
    return f'<div class="breakdown-card"><h4>By platform</h4><p class="note">{_esc(note)}</p>{"".join(rows)}</div>'


def _by_question_type_card(aiquery_results):
    def _bucket(labels):
        if not aiquery_results:
            return None, None
        cell = [r for r in aiquery_results if r["prompt_label"] in labels]
        if not cell:
            return None, None
        named = sum(1 for r in cell if r.get("mentioned"))
        return named, len(cell)

    rows = []
    for title, labels in (("Discovery", _DISCOVERY_LABELS), ("Brand recall", _BRAND_LABELS),
                           ("Competitive", _COMPETITIVE_LABELS)):
        named, total = _bucket(labels)
        if total:
            rows.append(_bar(title, f"{named} / {total}", _pct(named, total)))
        else:
            rows.append(_bar(title, "not tested this pass", 0, pending=True))
    return (f'<div class="breakdown-card"><h4>By question type</h4>'
            f'<p class="note">Grouped by intent, not shown prompt-by-prompt &mdash; '
            f'exact wording stays out of the report.</p>{"".join(rows)}</div>')


def _citations_card(attribution=None):
    if not attribution:
        return ('<div class="breakdown-card"><h4>Where citations point</h4>'
                 '<div class="pending-block"><b>Not run this pass</b>'
                 'Attribution needs the Google/Foursquare listing data and a fetch of the '
                 "business's own site &mdash; runs alongside the NAP check.</div></div>")
    rows = "".join(
        f'<div class="bar-row"><span class="bl">{_esc(name)}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{min(100, count*20)}%"></div></div>'
        f'<span class="bv real">{count}</span></div>'
        for name, count in sorted(attribution.items(), key=lambda kv: -kv[1])
    )
    return (f'<div class="breakdown-card"><h4>Where citations point</h4>'
            f'<p class="note">Phone-number match only, v1 &mdash; "consistent with," not "confirmed from."</p>'
            f'{rows}</div>')


def _gbp_card(resolve):
    resolve = resolve or {}
    if resolve.get("rating") is None:
        reason = ("no Google Business Profile found" if resolve.get("profile_found")
                  else "no Google Places API key configured, or no profile found")
        return (f'<div class="breakdown-card"><h4>Business profile (Google)</h4>'
                f'<div class="pending-block"><b>Unavailable this pass</b>'
                f'Rating, review count, and review freshness pull from Google Places &mdash; {_esc(reason)}. '
                f'Not a sequencing gap like the others; this needs a key added before it can run at all.'
                f'</div></div>')
    return (f'<div class="breakdown-card"><h4>Business profile (Google)</h4>'
            f'<div class="bar-row"><span class="bl">Rating</span><div></div>'
            f'<span class="bv real">{_esc(resolve["rating"])}</span></div>'
            f'<div class="bar-row"><span class="bl">Reviews</span><div></div>'
            f'<span class="bv real">{_esc(resolve.get("review_count") or 0)}</span></div>'
            f'<div class="bar-row"><span class="bl">Newest review</span><div></div>'
            f'<span class="bv real">{_esc(resolve.get("newest_review_days"))} days ago</span></div>'
            f'<p class="note" style="margin-top:10px;">Verdict: {_esc(resolve.get("verdict"))}</p></div>')


def _derive_findings(business, checks_results, aiquery_results, listings_data=None):
    """Rule-based, from real check results only — never hardcoded per-client copy."""
    findings = []
    crawler = (checks_results or {}).get("crawler") if checks_results else None
    schema = (checks_results or {}).get("schema") if checks_results else None
    machine_view = (checks_results or {}).get("machine_view") if checks_results else None

    if crawler and crawler.get("passed") is False:
        findings.append(("AI crawlers are blocked from reading your site",
                          crawler["finding"] + " — this is the headline finding; "
                          "everything else here is secondary until it's fixed."))
    if machine_view and machine_view.get("passed") is False:
        findings.append(("A plain-request fetch can't find " + ", ".join(machine_view["missing"]),
                          "No AI retrieval agent runs your JavaScript. Whatever isn't in the raw "
                          "HTML doesn't exist as far as an AI answer is concerned."))
    if schema and schema.get("passed") is False:
        findings.append(("Your homepage's structured data has a problem",
                          schema["finding"] + " — this is likely part of why discovery "
                          "prompts come back empty."))
    inconsistent = [d for d in ((listings_data or {}).get("comparison") or {}).get("disagreements") or []
                    if d["severity"] == "inconsistent"]
    if inconsistent:
        fields = ", ".join(d["field"] for d in inconsistent)
        findings.append((f"Your listings disagree with each other on {fields}",
                          "Inconsistent data across directories is worse than a directory simply "
                          "missing a field — it signals unreliable information, not just incomplete."))
    if aiquery_results:
        total = len(aiquery_results)
        named = sum(1 for r in aiquery_results if r.get("mentioned"))
        discovery = [r for r in aiquery_results if r["prompt_label"] in _DISCOVERY_LABELS]
        discovery_named = sum(1 for r in discovery if r.get("mentioned"))
        if discovery and discovery_named == 0:
            findings.append((f"AI has no idea {business} exists for discovery-style questions",
                              f"Every discovery prompt (best/near-me/comparison/niche/event/award) "
                              f"came back with zero mentions ({discovery_named}/{len(discovery)})."))
        brand_named = sum(1 for r in aiquery_results if r["prompt_label"] in _BRAND_LABELS and r.get("mentioned"))
        if named > 0 and named == brand_named:
            findings.append((f"The only hits require the asker to already know {business}'s name",
                              "All mentions came from brand-recall prompts, not discovery — "
                              "that's recall, not being found."))
        if named == 0:
            findings.append((f"{business} was never named across this pass",
                              f"0 of {total} prompts mentioned {business} at all."))
    if not findings:
        findings.append(("No findings yet",
                          "Run the technical checks and/or the AI-query pass to populate this page."))
    return findings


def _findings_html(findings):
    items = []
    for i, (title, body) in enumerate(findings, 1):
        sev = "sev-high" if i <= 3 else ""
        items.append(f'<li class="{sev}"><div class="rank">{i}</div>'
                      f'<div><h3>{_esc(title)}</h3><p>{_esc(body)}</p></div></li>')
    return "".join(items)


def _schema_table(checks_results):
    c = (checks_results or {}).get("schema") if checks_results else None
    if not c or c.get("passed") is None:
        return ('<div class="pending-block"><b>Pending</b>Structured-data check hasn\'t run yet.</div>')
    pill = ('<span class="pill good"><span class="dot"></span>OK</span>' if c["passed"]
            else '<span class="pill warn"><span class="dot"></span>issue</span>')
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead>'
            f'<tbody><tr><td class="name">LocalBusiness schema (type, name, phone)</td>'
            f'<td>{pill}</td><td class="note">{_esc(c["finding"])}</td></tr></tbody></table></div>'
            f'<p style="margin-top:10px; font-size:12px; color:var(--gray);">'
            f'Address, hours and service-description checks aren\'t implemented in this pipeline yet — '
            f'only type, name and phone are validated.</p>')


def _machine_view_table(checks_results):
    c = (checks_results or {}).get("machine_view") if checks_results else None
    if not c or c.get("passed") is None:
        return '<div class="pending-block"><b>Pending</b>Machine-view check hasn\'t run yet.</div>'
    fields = list(c.get("present", [])) + list(c.get("missing", []))
    rows = []
    for field in fields:
        is_present = field in c.get("present", [])
        pill = ('<span class="pill good"><span class="dot"></span>present</span>' if is_present
                else '<span class="pill warn"><span class="dot"></span>missing</span>')
        rows.append(f'<tr><td class="name">{_esc(field)}</td><td>{pill}</td></tr>')
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Field</th><th>Status</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p style="margin-top:10px; font-size:12px; color:var(--gray);">'
            f'Checked against the plain-request HTML only, no JS run &mdash; this is what any AI '
            f'retrieval agent actually sees, whatever a JS-enabled human visitor sees is out of scope '
            f'here (would need a browser dependency).</p>')


def _crawler_table(checks_results):
    c = (checks_results or {}).get("crawler") if checks_results else None
    if not c or c.get("passed") is None:
        return '<div class="pending-block"><b>Pending</b>Crawler-access check hasn\'t run yet.</div>'
    blocked = set()
    if c["passed"] is False and "blocks:" in c["finding"]:
        blocked = {a.strip() for a in c["finding"].split("blocks:", 1)[1].split(",")}
    rows = []
    kind = {"GPTBot": "Training", "OAI-SearchBot": "Retrieval", "PerplexityBot": "Retrieval",
            "ClaudeBot": "Training", "Google-Extended": "Training", "Bingbot": "Retrieval",
            "*": "All agents"}
    for agent in checks_module.AI_BOTS:
        is_blocked = agent in blocked
        pill = ('<span class="pill warn"><span class="dot"></span>blocked</span>' if is_blocked
                else '<span class="pill good"><span class="dot"></span>allowed</span>')
        rows.append(f'<tr><td class="name">{_esc(agent)}</td><td class="note">{kind.get(agent, "")}</td>'
                    f'<td>{pill}</td></tr>')
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Agent</th><th>Type</th><th>Status</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


_FACTOR_LABELS = {"clarity": "Clarity / summarization", "eeat": "E-E-A-T",
                   "qa_format": "Q&amp;A format", "structure": "Section structure",
                   "structured_data": "Structured data"}


def _content_grade_block(checks_results):
    c = (checks_results or {}).get("content_grade") if checks_results else None
    if not c or c.get("composite") is None:
        return '<div class="pending-block"><b>Pending</b>Content-grade check hasn\'t run yet.</div>'
    factors = c["factors"]
    weights = c["weights"]
    rows = []
    for key, label in _FACTOR_LABELS.items():
        val = factors[key]
        kind = "good" if val >= 60 else "warn"
        rows.append(f'<tr><td class="name">{label} ({weights[key]}%)</td>'
                    f'<td class="r">{val}/100</td>'
                    f'<td><span class="pill {kind}"><span class="dot"></span>'
                    f'{"ok" if val >= 60 else "weak"}</span></td></tr>')
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Factor (OD-1 weight)</th><th>Score</th><th></th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p style="margin-top:10px; font-size:14px;"><b>Weighted composite: {c["composite"]}/100</b></p>'
            f'<p style="margin-top:6px; font-size:12px; color:var(--gray);">'
            f'Homepage only, heuristic v1 of OD-1\'s 5-factor grade &mdash; each factor shown separately '
            f'per OD-1\'s own instruction, never collapsed straight to the composite. Not per service page yet.</p>')


def _sitemap_block(checks_results):
    c = (checks_results or {}).get("sitemap") if checks_results else None
    if not c or c.get("passed") is None:
        return '<div class="pending-block"><b>Pending</b>Sitemap check hasn\'t run yet.</div>'
    pill = ('<span class="pill good"><span class="dot"></span>found</span>' if c["passed"]
            else '<span class="pill warn"><span class="dot"></span>missing</span>')
    return f'<p>{pill} &mdash; {_esc(c["finding"])}</p>'


def _confusion_block(confusion):
    if not confusion:
        return '<div class="pending-block"><b>Pending</b>Confusion check hasn\'t run yet.</div>'
    flagged = confusion.get("flagged") or []
    if not flagged:
        return f'<p><span class="pill good"><span class="dot"></span>clear</span> &mdash; {_esc(confusion["finding"])}</p>'
    rows = "".join(f'<li style="margin-bottom:8px;"><i>&ldquo;{_esc(f["quote"])}&rdquo;</i> '
                    f'<span style="color:var(--gray); font-size:12px;">({_esc(f["prompt_label"])})</span></li>'
                    for f in flagged)
    return (f'<p><span class="pill warn"><span class="dot"></span>flagged</span> &mdash; {_esc(confusion["finding"])}</p>'
            f'<ul style="margin:8px 0 0 18px;">{rows}</ul>'
            f'<p style="margin-top:8px; font-size:12px; color:var(--gray);">Heuristic v1 &mdash; flags for human '
            f'review, does not auto-correct. The full design wants a per-client blocklist built from real cases.</p>')


def _bing_apple_block(checks_results):
    bing = (checks_results or {}).get("bing") if checks_results else None
    bing_html = '<div class="pending-block"><b>Pending</b>Bing indexing check hasn\'t run yet.</div>'
    if bing and bing.get("passed") is not None:
        pill = ('<span class="pill good"><span class="dot"></span>indexed</span>' if bing["passed"]
                else '<span class="pill warn"><span class="dot"></span>not indexed</span>')
        bing_html = f'<p><b>Bing indexing:</b> {pill} &mdash; {_esc(bing["finding"])}</p>'
    return (bing_html +
            '<div class="pending-block" style="margin-top:10px;">'
            '<b>Bing Places listing status &mdash; not built</b> No public API for looking up an arbitrary '
            "business's Bing Places listing was found (Bing Maps' own API is geocoding-only: address in, "
            'coordinates out &mdash; no phone/hours/listing status).</div>'
            '<div class="pending-block" style="margin-top:10px;">'
            '<b>Apple Maps &mdash; not built</b> No accessible public API for looking up an arbitrary business '
            "on Apple Maps / Apple Business Connect was found, and the master build brief doesn't specify one "
            "either &mdash; this is a real, acknowledged gap, not an oversight.</div>")


def _quotes_block(aiquery_results):
    if not aiquery_results:
        return ('<div class="pending-block"><b>Pending &mdash; needs the AI-query pass</b>'
                'No answers logged yet for this run.</div>')
    named = [r for r in aiquery_results if r.get("mentioned") and r.get("quote")]
    if not named:
        return ('<div class="pending-block"><b>No mentions to quote</b>'
                'None of this pass\'s answers named the business.</div>')
    items = "".join(f'<p style="font-style:italic; margin:0 0 10px;">'
                     f'&ldquo;{_esc(r["quote"])}&rdquo; <span style="color:var(--gray); font-style:normal; '
                     f'font-size:12px;">&mdash; {_esc(r["engine"])}</span></p>' for r in named[:6])
    return items


def _listings_section(listings_data):
    """SPEC-8 check 6: name/address/phone/hours/category across Google/Yelp/
    Foursquare. "Inconsistent" is shown as strictly worse than "missing"."""
    if not listings_data:
        return '<div class="pending-block"><b>Pending</b>Listings/NAP check hasn\'t run yet.</div>'

    sources = listings_data.get("sources") or {}
    comparison = listings_data.get("comparison") or {}
    usable = comparison.get("sources_used") or []

    side_rows = []
    for name, d in sources.items():
        if not d:
            continue
        status = ('<span class="pill good"><span class="dot"></span>found</span>' if d.get("found")
                  else '<span class="pill pending"><span class="dot"></span>no key / not found</span>')
        side_rows.append(
            f'<tr><td class="name">{_esc(name)}</td><td>{status}</td>'
            f'<td class="note">{_esc(d.get("name") or "—")}</td>'
            f'<td class="note">{_esc(d.get("address") or "—")}</td>'
            f'<td class="note">{_esc(d.get("phone") or "—")}</td>'
            f'<td class="note">{_esc(d.get("hours") or "—")}</td>'
            f'<td class="note">{_esc(d.get("category") or "—")}</td></tr>'
        )
    side_by_side = ""
    if side_rows:
        side_by_side = (
            '<div class="tbl-wrap"><table><thead><tr><th>Source</th><th>Status</th><th>Name</th>'
            '<th>Address</th><th>Phone</th><th>Hours</th><th>Category</th></tr></thead>'
            f'<tbody>{"".join(side_rows)}</tbody></table></div>'
        )

    if len(usable) < 2:
        return side_by_side + (
            f'<div class="pending-block" style="margin-top:12px;"><b>Not enough sources configured to compare</b>'
            f'{len(usable)} of 3 listing sources (Google, Yelp, Foursquare) have a working key and a match '
            f'right now &mdash; need at least 2 to check for disagreements. This is a real gap waiting on '
            f'API keys, not a fake clean comparison.</div>'
        )

    disagreements = comparison.get("disagreements") or []
    if not disagreements:
        diff_html = '<p style="color:var(--good); font-size:13.5px;">All sources agree on every field checked.</p>'
    else:
        drows = []
        for d in disagreements:
            sev_pill = ('<span class="pill warn"><span class="dot"></span>inconsistent</span>'
                        if d["severity"] == "inconsistent" else
                        '<span class="pill pending"><span class="dot"></span>missing from some</span>')
            values = "; ".join(f"{name}: {v}" for name, v in d["values"].items())
            drows.append(f'<tr><td class="name">{_esc(d["field"])}</td><td>{sev_pill}</td>'
                         f'<td class="note">{_esc(values)}</td></tr>')
        diff_html = (
            '<div class="tbl-wrap"><table><thead><tr><th>Field</th><th>Severity</th>'
            f'<th>What each source says</th></tr></thead><tbody>{"".join(drows)}</tbody></table></div>'
        )
    return side_by_side + f'<div style="margin-top:14px;">{diff_html}</div>'


def _sentiment_block():
    return ('<div class="pending-block"><b>Not built in this pipeline yet</b>'
            'Sentiment classification (positive/neutral/negative per mention) doesn\'t exist in GeoAudit — '
            'that only exists in GeoMonitor\'s daily tracker (extract.py), a separate pipeline. '
            'Would need to be ported here to appear in an audit.</div>')


def _competitor_table(competitor_scores):
    if not competitor_scores:
        return '<p style="color:var(--gray); font-size:13.5px;">No competitors supplied for this run.</p>'
    rows = []
    for name, s in competitor_scores.items():
        total = s.get("total", 0)
        mentioned = s.get("mentioned", 0)
        rate = f"{_pct(mentioned, total)}% ({mentioned}/{total})" if total else "not scored yet"
        rows.append(f'<tr><td class="name">{_esc(name)}</td><td class="note">{_esc(rate)}</td></tr>')
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Business</th><th>Their mention rate</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p style="margin-top:16px; font-size:13px; color:var(--gray);">Same 23-prompt set, same '
            f'named-substring test as the business itself (SPEC-8 check 5) — genuinely comparable numbers, '
            f'not a guess.</p>')


def _actions_html(checks_results, aiquery_results, listings_data=None):
    actions = []
    crawler = (checks_results or {}).get("crawler") if checks_results else None
    schema = (checks_results or {}).get("schema") if checks_results else None
    machine_view = (checks_results or {}).get("machine_view") if checks_results else None
    if crawler and crawler.get("passed") is False:
        actions.append(("diy", "Unblock AI crawlers in robots.txt",
                         crawler["finding"]))
    if machine_view and machine_view.get("passed") is False:
        actions.append(("diy", "Put " + ", ".join(machine_view["missing"]) + " in the page's plain HTML",
                         "Not just visually on the page — in the raw response, before any script runs."))
    if schema and schema.get("passed") is False:
        actions.append(("diy", "Add or fix LocalBusiness structured data",
                         schema["finding"]))
    inconsistent_fields = [d["field"] for d in ((listings_data or {}).get("comparison") or {}).get("disagreements") or []
                           if d["severity"] == "inconsistent"]
    if inconsistent_fields:
        actions.append(("diy", "Fix conflicting " + ", ".join(inconsistent_fields) + " across your listings",
                         "Inconsistent is worse than missing — a mismatch reads as unreliable data, "
                         "not just an incomplete profile."))
    if aiquery_results:
        discovery = [r for r in aiquery_results if r["prompt_label"] in _DISCOVERY_LABELS]
        if discovery and sum(1 for r in discovery if r.get("mentioned")) == 0:
            actions.append(("diy", "Publish a page describing what you do in plain language",
                             "Every discovery prompt failed — AI can't cite a page that doesn't exist."))
    actions.append(("us", "Get cited on relevant directory or press pages",
                     "Citations are what convert a mention into a click — outreach, not a form fill."))
    actions.append(("us", "Re-run this audit across all 4 engines once fixes ship",
                     "Confirms the fix actually moved the number, not just the intent."))
    items = "".join(
        f'<li><span class="tag {tag}">{"DIY" if tag == "diy" else "RETAINER"}</span>'
        f'<div><strong>{_esc(title)}</strong><span class="desc">{_esc(desc)}</span></div></li>'
        for tag, title, desc in actions
    )
    return items


def generate_html_report(data, output_path):
    business = data.get("business", "")
    city = data.get("city", "")
    run_date = data.get("date", "")
    resolve = data.get("resolve") or {}
    checks_results = data.get("checks")
    aiquery_results = data.get("aiquery")
    competitor_scores = data.get("competitor_scores") or {}
    listings_data = data.get("listings")
    confusion = data.get("confusion")
    attribution = data.get("attribution")
    score = data.get("score")
    website = resolve.get("website", "")

    engines_used = sorted({r["engine"] for r in aiquery_results}) if aiquery_results else []
    total_prompts = len({r["prompt_label"] for r in aiquery_results}) if aiquery_results else 0

    findings = _derive_findings(business, checks_results, aiquery_results, listings_data)

    html_doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>The Audit &mdash; {_esc(business)}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{_CSS}</style>
</head>
<body>
<div class="shell">
  <header class="masthead">
    <div>
      <div class="brand">Big Dog Little Dog &middot; The Audit</div>
      <h1>{_esc(business)}</h1>
      <span class="badge-sample">{_esc(len(engines_used))} of 4 platforms &middot; {_esc(total_prompts)} of 23 prompts</span>
    </div>
    <div class="meta">
      {_esc(city)}<br>
      <b>{_esc(website)}</b><br>
      Prepared {_esc(run_date)}
    </div>
  </header>

  <nav class="toc" aria-label="Report pages">
    <a href="#p1" class="active"><span class="n">01</span> The score</a>
    <a href="#p2"><span class="n">02</span> What's wrong</a>
    <a href="#p3"><span class="n">03</span> Named instead</a>
    <a href="#p4"><span class="n">04</span> What to do</a>
    <a href="#p5"><span class="n">05</span> Limits of this reading</a>
    <a href="#p6"><span class="n">06</span> The subscription</a>
  </nav>

  <main>
    <section class="page" id="p1">
      <p class="eyebrow">Page 1 of 6</p>
      <h2>The score</h2>
      <p class="dek">Lower is better on every number here &mdash; a low score is a to-do list, not a grade.</p>

      <div class="score-row">
        {_crawler_card(checks_results)}
        {_schema_card(checks_results)}
        {_mention_rate_card(aiquery_results, business)}
      </div>

      {_composite_score_block(score)}

      <p class="subhead">AI mention rate, broken down</p>
      <div class="breakdown-grid">
        {_named_only_card(aiquery_results)}
        {_by_platform_card(aiquery_results)}
        {_by_question_type_card(aiquery_results)}
        {_citations_card(attribution)}
        {_gbp_card(resolve)}
      </div>
    </section>

    <section class="page" id="p2">
      <p class="eyebrow">Page 2 of 6</p>
      <h2>What's wrong</h2>
      <p class="dek">Ordered by what actually matters, in plain words.</p>

      <ol class="findings">{_findings_html(findings)}</ol>

      <p class="subhead">Structured data</p>
      {_schema_table(checks_results)}

      <p class="subhead">What a machine sees (plain-request HTML, no JS)</p>
      {_machine_view_table(checks_results)}

      <p class="subhead">Crawler access, agent by agent</p>
      {_crawler_table(checks_results)}

      <p class="subhead">Content grade (OD-1's 5 factors)</p>
      {_content_grade_block(checks_results)}

      <p class="subhead">Sitemap</p>
      {_sitemap_block(checks_results)}

      <p class="subhead">Being confused with another business</p>
      {_confusion_block(confusion)}

      <p class="subhead">Bing, and Apple Maps</p>
      {_bing_apple_block(checks_results)}

      <p class="subhead">Listings consistency (name, address, phone, hours, category)</p>
      {_listings_section(listings_data)}

      <p class="subhead">What AI actually said</p>
      <div>{_quotes_block(aiquery_results)}</div>

      <p class="subhead" style="margin-top:24px;">Tone of the mentions you did get</p>
      {_sentiment_block()}
    </section>

    <section class="page" id="p3">
      <p class="eyebrow">Page 3 of 6</p>
      <h2>Who's being named instead</h2>
      <p class="dek">Not a critique of their sites &mdash; just who AI reaches for when it doesn't reach for you.</p>
      {_competitor_table(competitor_scores)}
    </section>

    <section class="page" id="p4">
      <p class="eyebrow">Page 4 of 6</p>
      <h2>What to do, in order</h2>
      <p class="dek">What you can do yourself is marked. The rest is retainer work.</p>
      <ul class="actions">{_actions_html(checks_results, aiquery_results, listings_data)}</ul>
    </section>

    <section class="page" id="p5">
      <p class="eyebrow">Page 5 of 6</p>
      <h2>What this reading can't tell you</h2>
      <p class="dek">This is the argument for a subscription, not a disclaimer bolted on at the end.</p>

      <div class="limit-grid">
        <div class="limit-card"><h3>One date, one reading</h3><p>No trend. We can't yet say whether this is typical or an unlucky day.</p></div>
        <div class="limit-card"><h3>{_esc(len(engines_used))} of 4 platforms</h3><p>{_esc(", ".join(engines_used) or "None run yet")}. The others may answer differently.</p></div>
        <div class="limit-card"><h3>Personalization</h3><p>AI answers can vary by account and session &mdash; untested here.</p></div>
        <div class="limit-card"><h3>{_esc(total_prompts)} of 23 prompts</h3><p>The full SPEC-8 set is 23 prompts across discovery, brand and competitive intent.</p></div>
      </div>

      <div class="argument">"This is one reading. It has no direction. Knowing whether a fix worked needs a second and a third."</div>
    </section>

    <section class="page" id="p6">
      <p class="eyebrow">Page 6 of 6</p>
      <h2>What a subscription adds</h2>
      <p class="dek">Same method, run on a schedule instead of once.</p>

      <div class="compare">
        <div class="col now">
          <h3>This audit</h3>
          <ul>
            <li>One date</li>
            <li>{_esc(len(engines_used))} of 4 platforms</li>
            <li>{_esc(total_prompts)} of 23 prompts</li>
            <li>No trend line</li>
          </ul>
        </div>
        <div class="col sub">
          <h3>Monthly tracking</h3>
          <ul>
            <li>Every week, automatically</li>
            <li>All 4 platforms</li>
            <li>Full 23-prompt set</li>
            <li>Trend + variance, catches regressions before they cost a client</li>
          </ul>
        </div>
      </div>
    </section>
  </main>

  <footer class="doc">Big Dog Little Dog &middot; SPEC-8 audit report &middot; generated {_esc(run_date)}</footer>
</div>

<script>
(function(){{
  try{{
    var links=[].slice.call(document.querySelectorAll('nav.toc a'));
    var sections=links.map(function(a){{return document.querySelector(a.getAttribute('href'));}});
    function onScroll(){{
      var y=window.scrollY+120;
      var idx=0;
      for(var i=0;i<sections.length;i++){{ if(sections[i] && sections[i].offsetTop<=y) idx=i; }}
      links.forEach(function(a,i){{ a.classList.toggle('active', i===idx); }});
    }}
    document.addEventListener('scroll', onScroll, {{passive:true}});
    onScroll();
  }}catch(e){{}}
}})();
</script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return output_path
