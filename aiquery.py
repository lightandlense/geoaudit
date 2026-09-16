"""Runs the 5 buyer prompts against ChatGPT, Perplexity, and Gemini (with search)."""
import os
import re
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import requests

PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "prompts.toml")
MAX_QUOTE_WORDS = 40


def load_prompts(business, city, industry):
    with open(PROMPTS_PATH, "rb") as f:
        data = tomllib.load(f)
    filled = []
    for p in data["prompts"]:
        text = p["template"].format(business=business, city=city, industry=industry)
        filled.append({"label": p["label"], "text": text})
    return filled


def _truncate(text, max_words=MAX_QUOTE_WORDS):
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _quote_sentence(answer, business):
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    if not sentences:
        return _truncate(answer)
    for s in sentences:
        if business.lower() in s.lower():
            return _truncate(s)
    return _truncate(sentences[0])


def _query_openai(prompt_text):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.responses.create(
        model="gpt-4o",
        input=prompt_text,
        tools=[{"type": "web_search"}],
    )
    return resp.output_text


def _query_perplexity(prompt_text):
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"},
        json={
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt_text}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _query_gemini(prompt_text):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt_text,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        ),
    )
    return resp.text


def _query_claude(prompt_text):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": prompt_text}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


ENGINES = {
    "ChatGPT": _query_openai,
    "Perplexity": _query_perplexity,
    "Gemini": _query_gemini,
    "Claude": _query_claude,
}


def _competitors_in(answer, competitors):
    """Same substring test used for the business itself, applied to each competitor name."""
    answer_lower = answer.lower()
    return [c for c in competitors if c.lower() in answer_lower]


_URL_RE = re.compile(r"https?://\S+")


def _cited(answer):
    """Heuristic v1: a URL appears in the answer text.

    ponytail: SPEC-3's real citeRate wants each engine's structured citation
    blocks (Claude/OpenAI's web_search results carry real URLs + positions),
    not this regex. None of the four _query_* functions here return anything
    but plain text right now, so there is nothing structured to read.
    Upgrade when the engine functions are changed to return citations
    alongside the answer text.
    """
    return bool(_URL_RE.search(answer))


def run_all(business, city, industry, on_progress=None, engines=None, competitors=None, samples=1):
    """Returns a list of cells: engine, prompt_label, sample, mentioned,
    quote, error, competitors_mentioned.

    engines: optional {name: fn} override, e.g. {"Claude": _query_claude} for a
    single-engine run. Defaults to all of ENGINES.
    competitors: optional list of competitor names, checked (case-insensitive
    substring, same test as `mentioned`) against the same answer text already
    fetched for the business — no extra API calls. Empty list per result when
    not passed or none matched.
    samples: how many times to repeat each (prompt, engine) pair. Default 1,
    matching SPEC-8's own 23 prompts x 4 platforms x 1 run = 92 math — this
    is a knob for whoever runs the audit to change, not a default this code
    should pick for them (open question, see AUDIT-REPORT.html footer's
    "three runs each" vs. SPEC-8's stated 92).
    """
    engines = engines if engines is not None else ENGINES
    competitors = competitors or []
    prompts = load_prompts(business, city, industry)
    results = []
    for prompt in prompts:
        for engine_name, engine_fn in engines.items():
            for s in range(samples):
                if on_progress:
                    on_progress(engine_name, prompt["label"])
                try:
                    answer = engine_fn(prompt["text"])
                    mentioned = business.lower() in answer.lower()
                    results.append({
                        "engine": engine_name,
                        "prompt_label": prompt["label"],
                        "sample": s,
                        "mentioned": mentioned,
                        "cited": mentioned and _cited(answer),
                        "quote": _quote_sentence(answer, business),
                        "error": None,
                        "competitors_mentioned": _competitors_in(answer, competitors),
                    })
                except Exception as e:
                    results.append({
                        "engine": engine_name,
                        "prompt_label": prompt["label"],
                        "sample": s,
                        "mentioned": None,
                        "cited": None,
                        "quote": None,
                        "error": "could not verify",
                        "competitors_mentioned": [],
                    })
    return results


def business_rates(results):
    """AI-channel numbers for the SPEC-3 score: mention rate, cite rate (of
    mentions, not of all runs), and platform rate (fraction of engines that
    named the business at least once). A run that errored is excluded from
    every denominator, not counted as a miss — a timeout is not a zero."""
    checked = [r for r in results if r.get("error") is None]
    n = len(checked)
    mentioned = sum(1 for r in checked if r["mentioned"])
    cited = sum(1 for r in checked if r["cited"])
    engines = {r["engine"] for r in checked}
    engines_mentioned = {r["engine"] for r in checked if r["mentioned"]}
    return {
        "mention_rate": mentioned / n if n else 0.0,
        "cite_rate": (cited / mentioned) if mentioned else 0.0,
        "platform_rate": (len(engines_mentioned) / len(engines)) if engines else 0.0,
        "checked": n,
        "mentioned": mentioned,
        "cited": cited,
        "platforms_mentioned": len(engines_mentioned),
        "platforms_checked": len(engines),
    }


def score_competitors(results, competitors):
    """Rolls up competitors_mentioned into the same {mentioned, total} shape as
    the business's own mention rate, so the two are directly comparable
    (SPEC-8 check 5: 'score the top three the same way'). Errored runs are
    excluded from the denominator, same reasoning as business_rates()."""
    checked = [r for r in results if r.get("error") is None]
    total = len(checked)
    return {
        name: {
            "mentioned": sum(1 for r in checked if name in r["competitors_mentioned"]),
            "total": total,
        }
        for name in competitors
    }
