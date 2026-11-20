import os
import re
import csv
import json
import html
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import quote

# ============================================================
# SPICY PARTY GAMES — PRODUCTION STATIC WEBSITE GENERATOR
# Python 3 | Zero Dependencies | Cloudflare Pages / Workers
# ============================================================

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://spicy-party-games.velvetgrid.workers.dev"
).rstrip("/")

SITE_NAME = "Spicy Party Games"
NICHE_TOPIC = "Interactive Adult Party Card Games, Never Have I Ever & Dare Decks"
CONTACT_EMAIL = "nancympatten@gmail.com"
AFFILIATE_URL = "#affiliate-link"
AFFILIATE_CTA_TEXT = "Unlock Live Interactive Party Rooms & Adult Shows"
CURRENT_YEAR = datetime.utcnow().year

CSV_FILE = "data.csv"
OUTPUT_DIR = "dist"
ITEMS_PER_PAGE = 24
RELATED_LIMIT = 8
NEWEST_LIMIT = 30

CSV_COLUMNS = [
    "slug",
    "title",
    "category",
    "subcategory",
    "target_keyword",
    "deck_prompts",
    "party_rules",
    "description",
    "tags",
    "faq_q1",
    "faq_a1",
    "faq_q2",
    "faq_a2",
    "upload_date",
]

# ============================================================
# UTILITIES
# ============================================================

def esc(value):
    return html.escape(str(value or ""), quote=True)


def clean(value):
    return str(value or "").strip()


def slugify(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "uncategorized"


def safe_slug(value):
    value = slugify(value)
    return value[:100]


def safe_date(value):
    value = clean(value)
    if not value:
        return datetime.utcnow().strftime("%Y-%m-%d")

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.utcnow().strftime("%Y-%m-%d")


def parse_tags(value):
    if not value:
        return []

    raw = re.split(r"[,;|]", clean(value))
    seen = set()
    result = []

    for tag in raw:
        tag = clean(tag)
        key = tag.lower()

        if tag and key not in seen:
            seen.add(key)
            result.append(tag)

    return result


def parse_prompts(value):
    prompts = [clean(x) for x in str(value or "").split("|")]
    return [x for x in prompts if x]


def write_file(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def json_script(data):
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def absolute_url(path):
    return BASE_URL + "/" + path.lstrip("/")


def page_url(path):
    return absolute_url(path)


def truncate(value, limit=155):
    value = clean(value)
    if len(value) <= limit:
        return value
    return value[:limit - 3].rsplit(" ", 1)[0] + "..."


def unique_records(records):
    seen = set()
    result = []

    for record in records:
        key = record["slug"]

        if key not in seen:
            seen.add(key)
            result.append(record)

    return result


def load_csv():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(
            f"Missing {CSV_FILE}. Create it using the required CSV schema."
        )

    records = []
    used_slugs = set()

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                "data.csv is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for line_number, row in enumerate(reader, start=2):
            record = {
                key: clean(row.get(key, ""))
                for key in CSV_COLUMNS
            }

            if not record["title"]:
                print(f"Skipping row {line_number}: missing title.")
                continue

            base_slug = safe_slug(
                record["slug"] or record["title"]
            )

            slug = base_slug
            suffix = 2

            while slug in used_slugs:
                slug = f"{base_slug}-{suffix}"
                suffix += 1

            used_slugs.add(slug)

            record["slug"] = slug
            record["category"] = record["category"] or "General"
            record["subcategory"] = (
                record["subcategory"] or record["category"]
            )
            record["target_keyword"] = (
                record["target_keyword"] or record["title"]
            )
            record["description"] = (
                record["description"]
                or f"Discover {record['title']}, an interactive adult party game."
            )
            record["party_rules"] = (
                record["party_rules"]
                or "Take turns, respect everyone's boundaries, and allow players to skip any prompt."
            )
            record["upload_date"] = safe_date(record["upload_date"])
            record["_tags"] = parse_tags(record["tags"])
            record["_prompts"] = parse_prompts(record["deck_prompts"])

            if not record["_prompts"]:
                record["_prompts"] = [
                    "Share a funny story from your life.",
                    "Describe your ideal party.",
                    "Give someone a genuine compliment.",
                    "Tell the group about a memorable adventure.",
                    "Share a harmless unpopular opinion.",
                    "Choose a song everyone should hear.",
                    "Describe your dream celebration.",
                    "Share something unexpected about yourself.",
                ]

            # Keep the interactive deck consistent with its eight-card design.
            record["_prompts"] = record["_prompts"][:8]

            records.append(record)

    if not records:
        raise ValueError("No valid records were found in data.csv.")

    return records


# ============================================================
# SHARED DESIGN SYSTEM
# ============================================================

CSS = r"""
:root {
    color-scheme: dark;
    --bg: #0a0812;
    --card: #171226;
    --card2: #211832;
    --orange: #f97316;
    --pink: #ec4899;
    --text: #f8f5ff;
    --muted: #aaa0ba;
    --border: rgba(255,255,255,.09);
    --radius: 18px;
    --max: 1160px;
}

* { box-sizing: border-box; }

html {
    scroll-behavior: smooth;
    background: var(--bg);
}

body {
    margin: 0;
    background:
        radial-gradient(ellipse at 15% 0%, rgba(236,72,153,.10), transparent 38%),
        radial-gradient(ellipse at 90% 15%, rgba(249,115,22,.09), transparent 35%),
        var(--bg);
    color: var(--text);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
                 BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.65;
}

a { color: inherit; text-decoration: none; }
a:hover { color: var(--orange); }

button, input { font: inherit; }

button {
    cursor: pointer;
    border: 0;
}

img { max-width: 100%; }

.container {
    width: min(var(--max), calc(100% - 36px));
    margin: auto;
}

.site-header {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(10,8,18,.93);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
}

.nav {
    min-height: 72px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
}

.logo {
    font-size: 21px;
    font-weight: 950;
    letter-spacing: -.8px;
}

.logo span {
    color: var(--orange);
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 22px;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--muted);
}

.hero {
    padding: 76px 0 55px;
    text-align: center;
}

.eyebrow {
    display: inline-flex;
    padding: 7px 13px;
    border-radius: 50px;
    color: #ffb47c;
    background: rgba(249,115,22,.12);
    border: 1px solid rgba(249,115,22,.25);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

h1 {
    font-size: clamp(34px, 6vw, 62px);
    line-height: 1.08;
    letter-spacing: -2px;
    margin: 22px 0;
}

h2 {
    font-size: clamp(23px, 3vw, 32px);
    letter-spacing: -.8px;
    line-height: 1.2;
}

h3 { line-height: 1.3; }

.gradient-text {
    background: linear-gradient(90deg, var(--orange), var(--pink));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.lead {
    color: var(--muted);
    max-width: 760px;
    margin: 0 auto;
    font-size: 17px;
}

.search-box {
    max-width: 690px;
    margin: 30px auto 0;
    display: flex;
    gap: 10px;
}

.search-box input {
    flex: 1;
    min-width: 0;
    padding: 17px 20px;
    color: white;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 13px;
    outline: none;
}

.search-box input:focus {
    border-color: var(--orange);
}

.btn {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    padding: 13px 20px;
    border-radius: 12px;
    color: white;
    font-weight: 850;
    background: linear-gradient(110deg, var(--orange), #ea580c);
    transition: transform .2s, opacity .2s;
}

.btn:hover {
    color: white;
    transform: translateY(-2px);
}

.btn-pink {
    background: linear-gradient(110deg, var(--pink), #be185d);
}

.btn-outline {
    background: var(--card2);
    border: 1px solid var(--border);
}

.section { padding: 38px 0; }

.section-heading {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 22px;
}

.section-heading h2 { margin: 0; }

.muted { color: var(--muted); }

.grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 18px;
}

.deck-card, .panel {
    background: linear-gradient(145deg, var(--card), #130f1f);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
    transition: border-color .2s, transform .2s;
}

.deck-card:hover {
    transform: translateY(-3px);
    border-color: rgba(249,115,22,.5);
}

.deck-card h3 { margin: 8px 0; }

.deck-card p {
    color: var(--muted);
    font-size: 14px;
}

.card-meta {
    color: #fda46c;
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
}

.pills, .tag-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
}

.pill {
    display: inline-flex;
    padding: 7px 12px;
    border-radius: 50px;
    background: var(--card2);
    border: 1px solid var(--border);
    color: #e8dff5;
    font-size: 12px;
    font-weight: 700;
}

.pill:hover {
    border-color: var(--orange);
}

.count {
    color: var(--orange);
    margin-left: 5px;
}

.deck-layout {
    display: grid;
    grid-template-columns: minmax(0,1.5fr) minmax(250px,.7fr);
    gap: 22px;
    align-items: start;
}

.game-stage {
    background:
        radial-gradient(ellipse at 50% 0%, rgba(236,72,153,.17), transparent 55%),
        var(--card);
    border: 1px solid rgba(236,72,153,.25);
    padding: clamp(20px, 4vw, 38px);
    border-radius: 24px;
    text-align: center;
}

.game-card {
    min-height: 260px;
    padding: 35px 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    border-radius: 20px;
    margin: 20px 0;
    background: linear-gradient(145deg, #28183d, #181026);
    border: 1px solid rgba(249,115,22,.28);
    box-shadow: 0 15px 55px rgba(0,0,0,.25);
}

.game-card .card-number {
    font-size: 12px;
    letter-spacing: 2px;
    color: var(--orange);
    font-weight: 900;
}

.game-card .prompt {
    font-size: clamp(23px, 4vw, 35px);
    line-height: 1.3;
    font-weight: 900;
    max-width: 580px;
    margin: 15px auto;
}

.game-controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
}

.game-controls .btn { flex: 1 1 145px; }

.counter {
    font-size: 13px;
    color: var(--muted);
    margin: 12px;
}

.player-input {
    width: 100%;
    background: #0d0a16;
    border: 1px solid var(--border);
    padding: 13px;
    border-radius: 11px;
    color: white;
    margin: 8px 0 12px;
    outline: none;
}

.player-result {
    margin: 12px 0;
    color: var(--orange);
    font-weight: 900;
    font-size: 20px;
    min-height: 30px;
}

.house-rules {
    margin-top: 22px;
    padding: 23px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--card);
}

details summary {
    cursor: pointer;
    font-weight: 900;
    font-size: 17px;
}

details p {
    color: var(--muted);
    white-space: pre-wrap;
}

.affiliate {
    margin: 24px 0;
    padding: 27px;
    text-align: center;
    border-radius: 20px;
    border: 1px solid rgba(236,72,153,.32);
    background: linear-gradient(120deg, rgba(236,72,153,.13),
                                     rgba(249,115,22,.12));
}

.affiliate h3 { margin-top: 0; }

.status-badge {
    display: inline-block;
    margin: 12px 0;
    padding: 7px 13px;
    border-radius: 30px;
    color: #ffbd8d;
    background: rgba(249,115,22,.12);
    border: 1px solid rgba(249,115,22,.3);
    font-size: 12px;
    font-weight: 900;
}

.breadcrumbs {
    font-size: 12px;
    color: var(--muted);
    margin: 24px 0;
}

.faq-item {
    padding: 17px 0;
    border-bottom: 1px solid var(--border);
}

.faq-item h3 { font-size: 16px; }
.faq-item p { color: var(--muted); }

.pagination {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 10px;
    margin: 35px 0;
}

.pagination a, .pagination span {
    padding: 10px 15px;
    border-radius: 10px;
    background: var(--card);
    border: 1px solid var(--border);
}

.pagination .current {
    background: var(--orange);
    color: white;
}

.site-footer {
    margin-top: 65px;
    padding: 40px 0;
    border-top: 1px solid var(--border);
    background: rgba(10,8,18,.7);
}

.footer-grid {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: 28px;
}

.footer-grid p, .footer-grid a {
    color: var(--muted);
    font-size: 13px;
}

.footer-links {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 20px;
}

.empty-state {
    padding: 35px;
    text-align: center;
    color: var(--muted);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
}

.age-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(5,3,10,.96);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.age-box {
    max-width: 440px;
    width: 100%;
    background: var(--card);
    padding: 32px;
    border: 1px solid rgba(249,115,22,.35);
    border-radius: 22px;
    text-align: center;
}

.age-box h2 { margin-top: 0; }

.age-actions {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 22px;
}

.ad-slot { min-height: 0; }

.hidden { display: none !important; }

@media(max-width:800px) {
    .grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
    .deck-layout { grid-template-columns: 1fr; }
    .footer-grid { grid-template-columns: 1fr 1fr; }
}

@media(max-width:560px) {
    .container { width: min(100% - 24px, var(--max)); }
    .nav { padding: 12px 0; align-items: flex-start; flex-direction: column; }
    .nav-links { gap: 13px; }
    .hero { padding: 48px 0 30px; }
    .search-box { flex-direction: column; }
    .grid { grid-template-columns: 1fr; }
    .footer-grid { grid-template-columns: 1fr; }
    .game-card { min-height: 235px; }
}
"""

# ============================================================
# SHARED JAVASCRIPT
# ============================================================

SHARED_JS = r"""
(function () {
    'use strict';

    const year = new Date().getFullYear();

    document.querySelectorAll('.live-year').forEach(function (el) {
        el.textContent = year;
    });

    const month = new Intl.DateTimeFormat(undefined, {
        month: 'long'
    }).format(new Date());

    document.querySelectorAll('.party-edition').forEach(function (el) {
        el.textContent = 'Party-Ready Edition • ' + month + ' ' + year;
    });

    const ageKey = 'spicyPartyAgeVerifiedV1';
    const overlay = document.getElementById('ageOverlay');

    if (overlay) {
        if (localStorage.getItem(ageKey) === 'yes') {
            overlay.classList.add('hidden');
            overlay.setAttribute('aria-hidden', 'true');
        }

        const confirm = document.getElementById('ageConfirm');
        const decline = document.getElementById('ageDecline');

        if (confirm) {
            confirm.addEventListener('click', function () {
                localStorage.setItem(ageKey, 'yes');
                overlay.classList.add('hidden');
                overlay.setAttribute('aria-hidden', 'true');
            });
        }

        if (decline) {
            decline.addEventListener('click', function () {
                window.location.replace('https://www.google.com/');
            });
        }
    }
})();
"""

DETAIL_JS = r"""
(function () {
    'use strict';

    const deckElement = document.getElementById('partyDeckData');
    if (!deckElement) return;

    let prompts = [];

    try {
        prompts = JSON.parse(deckElement.textContent);
    } catch (error) {
        console.error('Unable to read party deck data.', error);
        return;
    }

    if (!Array.isArray(prompts) || prompts.length === 0) return;

    let deck = prompts.slice();
    let currentIndex = -1;
    let drawn = 0;

    const promptElement = document.getElementById('currentPrompt');
    const numberElement = document.getElementById('cardNumber');
    const counterElement = document.getElementById('cardCounter');
    const nextButton = document.getElementById('drawNext');
    const shuffleButton = document.getElementById('shuffleDeck');
    const copyButton = document.getElementById('copyPrompts');

    function updateCounter() {
        counterElement.textContent =
            'Card Counter (' + Math.min(drawn, prompts.length) +
            '/' + prompts.length + ')';
    }

    function shuffle() {
        deck = prompts.slice();

        for (let i = deck.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [deck[i], deck[j]] = [deck[j], deck[i]];
        }

        currentIndex = -1;
        drawn = 0;

        promptElement.textContent = 'Your next party card is waiting...';
        numberElement.textContent = 'READY TO PLAY';
        updateCounter();
    }

    function draw() {
        if (currentIndex >= deck.length - 1) {
            shuffle();
        }

        currentIndex++;
        drawn++;

        promptElement.textContent = deck[currentIndex];
        numberElement.textContent =
            'PARTY CARD ' + drawn + ' OF ' + prompts.length;

        updateCounter();
    }

    function getPlayers() {
        const input = document.getElementById('playerNames');

        return input.value
            .split(',')
            .map(function (name) { return name.trim(); })
            .filter(Boolean);
    }

    function pickPlayer() {
        const players = getPlayers();
        const result = document.getElementById('playerResult');

        if (!players.length) {
            result.textContent = 'Add at least one player name first.';
            return;
        }

        const selected = players[Math.floor(Math.random() * players.length)];

        result.textContent = '🎉 ' + selected + ', it is your turn!';
    }

    nextButton.addEventListener('click', draw);
    shuffleButton.addEventListener('click', shuffle);

    document.getElementById('pickPlayer')
        .addEventListener('click', pickPlayer);

    copyButton.addEventListener('click', async function () {
        const text = prompts.map(function (prompt, index) {
            return (index + 1) + '. ' + prompt;
        }).join('\n');

        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();

                const success = document.execCommand('copy');
                textarea.remove();

                if (!success) throw new Error('Copy unavailable');
            }

            copyButton.textContent = 'Copied!';
            setTimeout(function () {
                copyButton.textContent = 'Copy All Prompts';
            }, 1800);

        } catch (error) {
            copyButton.textContent = 'Copy unavailable';
        }
    });

    shuffle();
})();
"""

SEARCH_JS = r"""
(function () {
    'use strict';

    const input = document.getElementById('deckSearch');
    if (!input) return;

    const cards = Array.from(document.querySelectorAll('[data-search-card]'));
    const empty = document.getElementById('searchEmpty');
    const count = document.getElementById('searchCount');

    input.addEventListener('input', function () {
        const query = input.value.trim().toLowerCase();
        let visible = 0;

        cards.forEach(function (card) {
            const haystack = card.dataset.searchCard.toLowerCase();
            const matches = !query || haystack.includes(query);

            card.classList.toggle('hidden', !matches);

            if (matches) visible++;
        });

        if (empty) {
            empty.classList.toggle('hidden', visible !== 0);
        }

        if (count) {
            count.textContent = visible + ' party decks found';
        }
    });
})();
"""

# ============================================================
# HTML BUILDING BLOCKS
# ============================================================

def age_modal():
    return """
    <div class="age-overlay" id="ageOverlay" role="dialog"
         aria-modal="true" aria-labelledby="ageTitle">
        <div class="age-box">
            <div class="eyebrow">Adults Only • 18+</div>
            <h2 id="ageTitle">Welcome to Spicy Party Games</h2>
            <p class="muted">
                This website contains adult-oriented party entertainment
                intended exclusively for visitors aged 18 or older.
            </p>
            <p class="muted">
                Please confirm that you meet the legal age requirement
                applicable to your location.
            </p>
            <div class="age-actions">
                <button class="btn" id="ageConfirm">I am 18 or older</button>
                <button class="btn btn-outline" id="ageDecline">
                    I am under 18
                </button>
            </div>
        </div>
    </div>
    """


def header():
    return """
    <header class="site-header">
        <div class="container nav">
            <a class="logo" href="/">
                SPICY<span> PARTY</span> GAMES
            </a>
            <nav class="nav-links" aria-label="Main navigation">
                <a href="/">Home</a>
                <a href="/#categories">Categories</a>
                <a href="/#newest">Newest Decks</a>
                <a href="/dmca.html">DMCA</a>
                <a href="/2257.html">Compliance</a>
            </nav>
        </div>
    </header>
    """


def footer():
    return f"""
    <footer class="site-footer">
        <div class="container">
            <div class="footer-grid">
                <div>
                    <a class="logo" href="/">
                        SPICY<span> PARTY</span> GAMES
                    </a>
                    <p>
                        Interactive adult party card games, conversation
                        starters, Never Have I Ever questions and playful
                        group challenges.
                    </p>
                    <p>Play responsibly. Respect boundaries. Everyone can skip.</p>
                </div>
                <div>
                    <h3>Explore</h3>
                    <p><a href="/">All Party Games</a></p>
                    <p><a href="/#categories">Categories</a></p>
                    <p><a href="/#newest">Latest Decks</a></p>
                </div>
                <div>
                    <h3>Information</h3>
                    <p><a href="/dmca.html">DMCA Policy</a></p>
                    <p><a href="/2257.html">18 U.S.C. § 2257 Statement</a></p>
                    <p><a href="mailto:{esc(CONTACT_EMAIL)}">Contact</a></p>
                </div>
            </div>
            <div class="footer-links">
                <span class="muted">
                    © <span class="live-year">{CURRENT_YEAR}</span>
                    {SITE_NAME}. All rights reserved.
                </span>
                <span class="muted">18+ Audience</span>
            </div>
        </div>
        <div style="background:#0d1018;border-top:1px solid #1f2433;padding:24px 16px;margin-top:40px;font-family:system-ui,-apple-system,sans-serif;text-align:center;">
          <p style="color:#9ca3af;font-size:12px;letter-spacing:1px;text-transform:uppercase;margin:0 0 12px 0;">Explore Our Interactive Network</p>
          <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;max-width:960px;margin:0 auto;">
            <a href="https://ai-girlfriend-prompts.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">AI Girlfriend Prompts</a>
            <a href="https://couples-intimacy-games.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Couples Intimacy Games</a>
            <a href="https://fantasy-roleplay-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Fantasy Roleplay Hub</a>
            <a href="https://character-persona-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Character Persona Hub</a>
            <a href="https://flirty-chat-openers.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Flirty Chat Openers</a>
            <a href="https://midnight-audio-stories.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Midnight Audio Stories</a>
            <a href="https://spicy-party-games.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Spicy Party Games</a>
            <a href="https://intimacy-quiz-hub.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Intimacy Quiz Hub</a>
            <a href="https://couples-bucket-list.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Couples Bucket List</a>
            <a href="https://adult-ai-art-prompts.velvetgrid.workers.dev" style="color:#c4b5fd;background:#161b28;padding:6px 12px;border-radius:6px;font-size:13px;text-decoration:none;border:1px solid #262d40;">Adult AI Art Prompts</a>
          </div>
        </div>
    </footer>
    """


def ad_slot(name):
    return f'<div class="ad-slot"><!-- AD_SLOT_{name} --></div>'


def meta_tags(title, description, canonical, og_type="website"):
    return f"""
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(truncate(description, 160))}">
    <meta name="robots" content="index,follow,max-image-preview:large">
    <meta name="google-site-verification" content="Ee2L9A2G2nVVNtBt7HiplcBJf1nSen-Rcz4sNqLuAdc" />
    <meta name="msvalidate.01" content="4573069C62AEC27DA4F08DC57760BAD4" />
    <meta name="rating" content="RTA-5042-1996-1400-1577-RTA" />
    <link rel="canonical" href="{esc(canonical)}">
    <meta property="og:type" content="{esc(og_type)}">
    <meta property="og:site_name" content="{esc(SITE_NAME)}">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(truncate(description, 200))}">
    <meta property="og:url" content="{esc(canonical)}">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{esc(title)}">
    <meta name="twitter:description" content="{esc(truncate(description, 200))}">
    """


def document(title, description, canonical, body, extra_head="",
             og_type="website", include_age=True, extra_scripts=""):
    age = age_modal() if include_age else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta_tags(title, description, canonical, og_type)}
<meta name="theme-color" content="#0a0812">
<meta name="author" content="{esc(SITE_NAME)}">
<meta name="referrer" content="strict-origin-when-cross-origin">
{extra_head}
<style>{CSS}</style>
</head>
<body>
{header()}
{ad_slot("TOP_BANNER")}
{body}
{footer()}
{age}
<script>{SHARED_JS}</script>
{extra_scripts}
</body>
</html>"""


def deck_card(record):
    url = "/deck/" + quote(record["slug"]) + ".html"

    search_text = " ".join([
        record["title"],
        record["target_keyword"],
        record["category"],
        record["subcategory"],
        " ".join(record["_tags"]),
    ])

    return f"""
    <article class="deck-card" data-search-card="{esc(search_text)}">
        <div class="card-meta">{esc(record['category'])}</div>
        <h3><a href="{url}">{esc(record['title'])}</a></h3>
        <p>{esc(truncate(record['description'], 135))}</p>
        <div class="pills">
            <span class="pill">{esc(record['subcategory'])}</span>
            <span class="pill">{len(record['_prompts'])} Cards</span>
        </div>
        <p><a class="btn" href="{url}">Play This Deck →</a></p>
    </article>
    """


def breadcrumb(items):
    parts = []

    for label, url in items:
        if url:
            parts.append(f'<a href="{esc(url)}">{esc(label)}</a>')
        else:
            parts.append(f'<span>{esc(label)}</span>')

    return '<nav class="breadcrumbs" aria-label="Breadcrumb">' + (
        " / ".join(parts)
    ) + '</nav>'


def schema_script(data):
    return (
        '<script type="application/ld+json">'
        + json_script(data)
        + '</script>'
    )


# ============================================================
# CATEGORY / SUBCATEGORY / TAG INDEXING
# ============================================================

def build_indexes(records):
    categories = defaultdict(list)
    subcategories = defaultdict(list)
    tags = defaultdict(list)

    for record in records:
        categories[record["category"]].append(record)
        subcategories[record["subcategory"]].append(record)

        for tag in record["_tags"]:
            tags[tag].append(record)

    return categories, subcategories, tags


# ============================================================
# DETAIL PAGE + STRUCTURED DATA
# ============================================================

def related_records(record, all_records):
    candidates = []

    for other in all_records:
        if other["slug"] == record["slug"]:
            continue

        score = 0

        if other["subcategory"].lower() == record["subcategory"].lower():
            score += 10

        if other["category"].lower() == record["category"].lower():
            score += 5

        shared = {
            x.lower() for x in record["_tags"]
        } & {
            x.lower() for x in other["_tags"]
        }

        score += len(shared) * 3

        candidates.append((score, other))

    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1]["title"].lower()
        )
    )

    return [item[1] for item in candidates[:RELATED_LIMIT]]


def build_detail_schema(record, related):
    canonical = page_url("deck/" + record["slug"] + ".html")

    howto_steps = [
        {
            "@type": "HowToStep",
            "position": 1,
            "name": "Gather your players",
            "text": "Invite adult participants and agree on comfortable boundaries."
        },
        {
            "@type": "HowToStep",
            "position": 2,
            "name": "Read the house rules",
            "text": record["party_rules"]
        },
        {
            "@type": "HowToStep",
            "position": 3,
            "name": "Choose the next player",
            "text": "Enter player names and use the random player picker."
        },
        {
            "@type": "HowToStep",
            "position": 4,
            "name": "Draw a party card",
            "text": "Click Draw Next Card and read the prompt aloud."
        },
        {
            "@type": "HowToStep",
            "position": 5,
            "name": "Continue the game",
            "text": "Take turns, respect personal boundaries, and allow anyone to skip a prompt."
        },
    ]

    howto = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": "How to Play " + record["title"],
        "description": truncate(record["description"], 200),
        "totalTime": "PT15M",
        "step": howto_steps,
        "supply": [
            {"@type": "HowToSupply", "name": "Internet-enabled device"},
            {"@type": "HowToSupply", "name": "Adult participants"},
        ],
        "tool": [
            {"@type": "HowToTool", "name": "Interactive party card deck"},
        ],
    }

    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": record["title"],
        "description": truncate(record["description"], 200),
        "datePublished": record["upload_date"],
        "dateModified": record["upload_date"],
        "mainEntityOfPage": canonical,
        "author": {
            "@type": "Organization",
            "name": SITE_NAME,
        },
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": BASE_URL,
        },
        "keywords": ", ".join(
            [record["target_keyword"]] + record["_tags"]
        ),
    }

    breadcrumb_data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": BASE_URL + "/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": record["category"],
                "item": page_url(
                    "category/" + slugify(record["category"]) + "/page-1.html"
                ),
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": record["title"],
                "item": canonical,
            },
        ],
    }

    faq_items = []

    for question, answer in [
        (record["faq_q1"], record["faq_a1"]),
        (record["faq_q2"], record["faq_a2"]),
    ]:
        if question and answer:
            faq_items.append({
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer,
                },
            })

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_items,
    }

    return [howto, article, breadcrumb_data, faq_schema]


def build_detail(record, all_records):
    slug = record["slug"]
    title = record["title"]
    canonical_path = "deck/" + slug + ".html"
    canonical = page_url(canonical_path)

    related = related_records(record, all_records)

    tags_html = "".join(
        f'<a class="pill" href="/tag/{slugify(tag)}.html">{esc(tag)}</a>'
        for tag in record["_tags"]
    )

    subcategory_link = (
        "/topic/" + slugify(record["subcategory"]) + ".html"
    )

    prompts_json = json_script(record["_prompts"])

    faq_html = ""

    for question, answer in [
        (record["faq_q1"], record["faq_a1"]),
        (record["faq_q2"], record["faq_a2"]),
    ]:
        if question and answer:
            faq_html += f"""
            <div class="faq-item">
                <h3>{esc(question)}</h3>
                <p>{esc(answer)}</p>
            </div>
            """

    related_html = "".join(deck_card(x) for x in related)

    schemas = "".join(
        schema_script(item)
        for item in build_detail_schema(record, related)
    )

    body = f"""
    <main class="container">
        {breadcrumb([
            ("Home", "/"),
            (record["category"], "/category/" + slugify(record["category"]) + "/page-1.html"),
            (title, None),
        ])}

        <section class="section">
            <span class="eyebrow">18+ Interactive Party Game</span>
            <h1>{esc(title)}</h1>
            <p class="lead">{esc(record['description'])}</p>

            <div class="pills" style="justify-content:center;margin-top:18px">
                <a class="pill" href="/category/{slugify(record['category'])}/page-1.html">
                    {esc(record['category'])}
                </a>
                <a class="pill" href="{subcategory_link}">
                    {esc(record['subcategory'])}
                </a>
                <span class="pill">8 Party Cards</span>
            </div>

            <div class="status-badge party-edition">
                Party-Ready Edition • {datetime.utcnow().strftime("%B %Y")}
            </div>
        </section>

        {ad_slot("MID_CONTENT")}

        <section class="deck-layout">
            <div class="game-stage">
                <span class="eyebrow">Interactive Party Deck Studio</span>
                <h2>Tap-to-Draw Party Cards</h2>

                <div class="game-card" aria-live="polite">
                    <div class="card-number" id="cardNumber">READY TO PLAY</div>
                    <div class="prompt" id="currentPrompt">
                        Your next party card is waiting...
                    </div>
                </div>

                <div class="counter" id="cardCounter">
                    Card Counter (0/{len(record['_prompts'])})
                </div>

                <div class="game-controls">
                    <button class="btn" id="drawNext">Draw Next Card</button>
                    <button class="btn btn-pink" id="shuffleDeck">Shuffle Deck</button>
                    <button class="btn btn-outline" id="copyPrompts">
                        Copy All Prompts
                    </button>
                </div>

                <script type="application/json" id="partyDeckData">{prompts_json}</script>

                <div class="house-rules">
                    <h3>Multiplayer Name Adder & Random Player Picker</h3>
                    <p class="muted">
                        Add player names separated by commas, then choose
                        whose turn comes next.
                    </p>
                    <label for="playerNames">Player names</label>
                    <input
                        class="player-input"
                        id="playerNames"
                        type="text"
                        placeholder="Alex, Jordan, Taylor, Sam"
                        autocomplete="off"
                    >
                    <button class="btn btn-pink" id="pickPlayer">
                        Pick Next Player
                    </button>
                    <div class="player-result" id="playerResult"
                         aria-live="polite"></div>
                </div>
            </div>

            <aside>
                <div class="panel">
                    <h3>How to Play</h3>
                    <ol class="muted">
                        <li>Gather your adult players.</li>
                        <li>Agree on boundaries and house rules.</li>
                        <li>Enter the player names.</li>
                        <li>Pick the next player.</li>
                        <li>Draw a card and enjoy the game.</li>
                    </ol>
                    <p class="muted">
                        Every player can skip a prompt without pressure.
                    </p>
                </div>

                <div class="panel" style="margin-top:16px">
                    <h3>Game Information</h3>
                    <p class="muted">Category: {esc(record['category'])}</p>
                    <p class="muted">Subcategory: {esc(record['subcategory'])}</p>
                    <p class="muted">Cards: {len(record['_prompts'])}</p>
                    <p class="muted">Published: {esc(record['upload_date'])}</p>
                </div>
            </aside>
        </section>

        <section class="affiliate">
            <span class="eyebrow">Take Your Party Further</span>
            <h3>{esc(AFFILIATE_CTA_TEXT)}</h3>
            <p class="muted">
                Discover additional entertainment and interactive
                experiences for your next adult party.
            </p>
            <a class="btn btn-pink" href="{esc(AFFILIATE_URL)}"
               rel="nofollow sponsored">
                Explore More Experiences →
            </a>
        </section>

        <section class="house-rules">
            <details>
                <summary>Official House Rules & Intensity Guide</summary>
                <p>{esc(record['party_rules'])}</p>
                <p>
                    Participation is voluntary. No one should be pressured
                    into sharing personal information, performing an action,
                    or consuming anything. Players can skip any card.
                </p>
            </details>
        </section>

        <section class="section">
            <h2>About This Party Game</h2>
            <p class="muted">{esc(record['description'])}</p>
            <p class="muted">
                Explore more ideas in
                <a href="{subcategory_link}">{esc(record['subcategory'])}</a>.
            </p>
            <div class="tag-cloud">{tags_html}</div>
        </section>

        {ad_slot("MID_CONTENT")}

        <section class="section">
            <h2>Frequently Asked Questions</h2>
            {faq_html if faq_html else '<p class="muted">Check the house rules above for information about this game.</p>'}
        </section>

        <section class="section">
            <div class="section-heading">
                <h2>Related Adult Party Games</h2>
            </div>
            <div class="grid">
                {related_html if related_html else '<p class="muted">More party games are coming soon.</p>'}
            </div>
        </section>
    </main>
    """

    path = os.path.join(OUTPUT_DIR, canonical_path)

    html_output = document(
        title=f"{title} | Interactive Adult Party Game",
        description=record["description"],
        canonical=canonical,
        body=body,
        extra_head=schemas,
        og_type="article",
        extra_scripts=f"<script>{DETAIL_JS}</script>",
    )

    write_file(path, html_output)


# ============================================================
# HOMEPAGE
# ============================================================

def build_home(records, categories, subcategories, tags):
    newest = sorted(
        records,
        key=lambda x: x["upload_date"],
        reverse=True
    )[:NEWEST_LIMIT]

    newest_html = "".join(deck_card(x) for x in newest)

    category_html = ""

    # Each unique category appears exactly once.
    for category in sorted(categories, key=str.lower):
        items = categories[category]
        category_slug = slugify(category)
        category_html += f"""
        <a class="deck-card" href="/category/{category_slug}/page-1.html">
            <div class="card-meta">PARTY GAME CATEGORY</div>
            <h3>{esc(category)}</h3>
            <p>Explore interactive games, party cards and group challenges.</p>
            <span class="pill">{len(items)} decks</span>
        </a>
        """

    subcategory_html = ""

    for name in sorted(subcategories, key=str.lower):
        subcategory_html += f"""
        <a class="pill" href="/topic/{slugify(name)}.html">
            {esc(name)} <span class="count">{len(subcategories[name])}</span>
        </a>
        """

    tag_html = ""

    for name in sorted(tags, key=str.lower):
        tag_html += f"""
        <a class="pill" href="/tag/{slugify(name)}.html">
            {esc(name)} <span class="count">{len(tags[name])}</span>
        </a>
        """

    all_cards = "".join(deck_card(x) for x in records)

    body = f"""
    <main class="container">
        <section class="hero">
            <span class="eyebrow">The Ultimate Adult Party Game Collection</span>
            <h1>
                Make Every Party<br>
                <span class="gradient-text">Unforgettable.</span>
            </h1>
            <p class="lead">
                Discover interactive adult party card games, Never Have I Ever
                questions, playful dares and multiplayer conversation decks.
                Pick a player, draw a card and get the party started.
            </p>
            <div class="search-box">
                <input
                    id="deckSearch"
                    type="search"
                    placeholder="Search party games, keywords or tags..."
                    aria-label="Search party games"
                >
                <a class="btn" href="#all-games">Explore Games</a>
            </div>
            <p class="muted" id="searchCount">{len(records)} party decks available</p>
            <div class="status-badge party-edition">
                Party-Ready Edition • {datetime.utcnow().strftime("%B %Y")}
            </div>
        </section>

        {ad_slot("MID_CONTENT")}

        <section class="section" id="categories">
            <div class="section-heading">
                <h2>Browse Party Game Categories</h2>
            </div>
            <div class="grid">
                {category_html}
            </div>
        </section>

        <section class="section">
            <div class="section-heading">
                <h2>Explore Subcategories</h2>
            </div>
            <div class="pills">{subcategory_html}</div>
        </section>

        <section class="section">
            <div class="section-heading">
                <h2>Popular Party Game Tags</h2>
            </div>
            <div class="tag-cloud">{tag_html}</div>
        </section>

        <section class="section" id="newest">
            <div class="section-heading">
                <h2>30 Newest Party Decks</h2>
            </div>
            <div class="grid">
                {newest_html}
            </div>
        </section>

        <section class="section" id="all-games">
            <div class="section-heading">
                <h2>Discover All Party Games</h2>
            </div>
            <div class="grid" id="allDecks">
                {all_cards}
            </div>
            <div class="empty-state hidden" id="searchEmpty">
                No matching party games found. Try another search.
            </div>
        </section>

        <section class="affiliate">
            <h2>Ready for an Unforgettable Night?</h2>
            <p class="muted">
                Discover more interactive entertainment and experiences.
            </p>
            <a class="btn btn-pink" href="{esc(AFFILIATE_URL)}"
               rel="nofollow sponsored">
                {esc(AFFILIATE_CTA_TEXT)}
            </a>
        </section>
    </main>
    """

    extra_head = schema_script({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": BASE_URL + "/",
        "description": NICHE_TOPIC,
    })

    html_output = document(
        title=f"{SITE_NAME} | Interactive Adult Party Card Games",
        description=(
            "Play interactive adult party card games, Never Have I Ever, "
            "conversation starters and multiplayer party dares."
        ),
        canonical=BASE_URL + "/",
        body=body,
        extra_head=extra_head,
        extra_scripts=f"<script>{SEARCH_JS}</script>",
    )

    write_file(os.path.join(OUTPUT_DIR, "index.html"), html_output)


# ============================================================
# CATEGORY HUBS WITH PAGINATION
# ============================================================

def build_category_pages(categories):
    for category, items in categories.items():
        category_slug = slugify(category)

        ordered = sorted(
            items,
            key=lambda x: (
                x["upload_date"],
                x["title"].lower()
            ),
            reverse=True
        )

        total_pages = max(
            1,
            math.ceil(len(ordered) / ITEMS_PER_PAGE)
        )

        for page_number in range(1, total_pages + 1):
            start = (page_number - 1) * ITEMS_PER_PAGE
            page_items = ordered[start:start + ITEMS_PER_PAGE]

            current_path = (
                f"category/{category_slug}/page-{page_number}.html"
            )

            canonical = page_url(current_path)

            prev_link = ""
            next_link = ""

            extra_head = ""

            if page_number > 1:
                previous_url = page_url(
                    f"category/{category_slug}/page-{page_number - 1}.html"
                )
                prev_link = (
                    f'<link rel="prev" href="{esc(previous_url)}">'
                )

            if page_number < total_pages:
                next_url = page_url(
                    f"category/{category_slug}/page-{page_number + 1}.html"
                )
                next_link = (
                    f'<link rel="next" href="{esc(next_url)}">'
                )

            extra_head += prev_link + next_link

            cards = "".join(deck_card(x) for x in page_items)

            pagination = ""

            for number in range(1, total_pages + 1):
                url = (
                    f"/category/{category_slug}/page-{number}.html"
                )

                if number == page_number:
                    pagination += (
                        f'<span class="current">{number}</span>'
                    )
                else:
                    pagination += f'<a href="{url}">{number}</a>'

            body = f"""
            <main class="container">
                {breadcrumb([
                    ("Home", "/"),
                    (category, None),
                ])}
                <section class="section">
                    <span class="eyebrow">Party Game Category</span>
                    <h1>{esc(category)} <span class="live-year">{CURRENT_YEAR}</span></h1>
                    <p class="lead">
                        Explore {len(ordered)} interactive party games in
                        this category. Discover new decks and group challenges.
                    </p>
                </section>
                <section class="section">
                    <div class="section-heading">
                        <h2>Browse {esc(category)} Games</h2>
                        <span class="muted">
                            Page {page_number} of {total_pages}
                        </span>
                    </div>
                    <div class="grid">{cards}</div>
                    <nav class="pagination" aria-label="Pagination">
                        {pagination}
                    </nav>
                </section>
            </main>
            """

            html_output = document(
                title=f"{category} Party Games | Page {page_number} | {SITE_NAME}",
                description=(
                    f"Browse {len(ordered)} {category} party games, "
                    "interactive cards and multiplayer challenges."
                ),
                canonical=canonical,
                body=body,
                extra_head=extra_head,
            )

            write_file(
                os.path.join(OUTPUT_DIR, current_path),
                html_output
            )


# ============================================================
# SUBCATEGORY AND TAG HUBS
# ============================================================

def build_collection_page(name, records, kind):
    if kind == "topic":
        relative = "topic/" + slugify(name) + ".html"
        heading = name + " Party Games"
        description = (
            f"Explore interactive {name} party games and multiplayer decks."
        )
    else:
        relative = "tag/" + slugify(name) + ".html"
        heading = name + " Party Games"
        description = (
            f"Discover party games and interactive decks tagged with {name}."
        )

    canonical = page_url(relative)

    ordered = sorted(
        records,
        key=lambda x: x["upload_date"],
        reverse=True
    )

    cards = "".join(deck_card(x) for x in ordered)

    body = f"""
    <main class="container">
        {breadcrumb([
            ("Home", "/"),
            (heading, None),
        ])}
        <section class="section">
            <span class="eyebrow">Explore the Collection</span>
            <h1>{esc(heading)}</h1>
            <p class="lead">{esc(description)}</p>
        </section>
        <section class="section">
            <div class="section-heading">
                <h2>{len(ordered)} Available Games</h2>
            </div>
            <div class="grid">{cards}</div>
        </section>
    </main>
    """

    html_output = document(
        title=f"{heading} | {SITE_NAME}",
        description=description,
        canonical=canonical,
        body=body,
    )

    write_file(
        os.path.join(OUTPUT_DIR, relative),
        html_output
    )


def build_collection_pages(subcategories, tags):
    for name, records in subcategories.items():
        build_collection_page(name, records, "topic")

    for name, records in tags.items():
        build_collection_page(name, records, "tag")


# ============================================================
# DMCA AND 2257 INFORMATION PAGES
# ============================================================

def build_legal_pages():
    dmca_body = f"""
    <main class="container">
        <section class="section">
            <span class="eyebrow">Website Policy</span>
            <h1>DMCA Copyright Policy</h1>
            <p class="muted">
                {SITE_NAME} respects intellectual property rights and
                expects contributors and visitors to do the same.
            </p>

            <div class="panel">
                <h2>Copyright Complaints</h2>
                <p class="muted">
                    If you believe material available on this website
                    infringes your copyright, send a written notice to
                    <a href="mailto:{esc(CONTACT_EMAIL)}">
                    {esc(CONTACT_EMAIL)}</a>.
                </p>

                <h3>Your notice should include:</h3>
                <ol class="muted">
                    <li>Your physical or electronic signature.</li>
                    <li>Identification of the copyrighted work.</li>
                    <li>Identification of the allegedly infringing material
                        and information sufficient to locate it.</li>
                    <li>Your contact information.</li>
                    <li>A statement of good-faith belief that the use is
                        unauthorized.</li>
                    <li>A statement, under penalty of perjury, that the
                        information is accurate and that you are authorized
                        to act for the copyright owner.</li>
                </ol>

                <h3>Counter-Notifications</h3>
                <p class="muted">
                    If material was removed in error, you may contact us
                    with a counter-notification containing the information
                    required by applicable copyright law.
                </p>

                <h3>Review and Removal</h3>
                <p class="muted">
                    We review properly submitted notices and may remove or
                    disable access to material when appropriate. Repeat
                    infringement may result in restrictions on access.
                </p>
            </div>
        </section>
    </main>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "dmca.html"),
        document(
            "DMCA Copyright Policy | " + SITE_NAME,
            "Read the copyright complaint and DMCA policy for Spicy Party Games.",
            page_url("dmca.html"),
            dmca_body,
        )
    )

    compliance_body = f"""
    <main class="container">
        <section class="section">
            <span class="eyebrow">Age & Content Information</span>
            <h1>18 U.S.C. § 2257 Compliance Statement</h1>

            <div class="panel">
                <p class="muted">
                    {SITE_NAME} is an interactive party-game and
                    text-based entertainment website.
                </p>

                <p class="muted">
                    The website publishes original or editorial
                    text-based game prompts, conversation starters,
                    game instructions, and related informational content.
                </p>

                <p class="muted">
                    This website does not knowingly publish visual
                    depictions of actual sexually explicit conduct.
                    Accordingly, the website's text-based editorial
                    material is not represented as requiring primary
                    producer records under 18 U.S.C. § 2257.
                </p>

                <p class="muted">
                    This statement is provided for informational purposes
                    and does not replace an assessment of applicable legal
                    requirements. Any third-party material, if present,
                    remains subject to its applicable legal obligations.
                </p>

                <h3>Contact</h3>
                <p class="muted">
                    Compliance questions:
                    <a href="mailto:{esc(CONTACT_EMAIL)}">
                    {esc(CONTACT_EMAIL)}</a>
                </p>

                <h3>Age Restriction</h3>
                <p class="muted">
                    This website is intended for adults aged 18 or older.
                    Visitors must satisfy the applicable age requirements
                    in their jurisdiction.
                </p>
            </div>
        </section>
    </main>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "2257.html"),
        document(
            "18 U.S.C. 2257 Statement | " + SITE_NAME,
            "Age and text-based content compliance information.",
            page_url("2257.html"),
            compliance_body,
        )
    )


# ============================================================
# SITEMAP XML AND DARK MODE STYLESHEET
# ============================================================

def build_sitemaps(records, categories, subcategories, tags):
    urls = []

    urls.append({
        "loc": page_url(""),
        "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
        "priority": "1.0",
        "changefreq": "weekly",
    })

    for record in records:
        urls.append({
            "loc": page_url("deck/" + record["slug"] + ".html"),
            "lastmod": record["upload_date"],
            "priority": "0.8",
            "changefreq": "monthly",
        })

    for category, items in categories.items():
        pages = max(
            1,
            math.ceil(len(items) / ITEMS_PER_PAGE)
        )

        for number in range(1, pages + 1):
            urls.append({
                "loc": page_url(
                    f"category/{slugify(category)}/page-{number}.html"
                ),
                "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
                "priority": "0.7",
                "changefreq": "weekly",
            })

    for name in subcategories:
        urls.append({
            "loc": page_url("topic/" + slugify(name) + ".html"),
            "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
            "priority": "0.6",
            "changefreq": "monthly",
        })

    for name in tags:
        urls.append({
            "loc": page_url("tag/" + slugify(name) + ".html"),
            "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
            "priority": "0.5",
            "changefreq": "monthly",
        })

    for path in ["dmca.html", "2257.html"]:
        urls.append({
            "loc": page_url(path),
            "lastmod": datetime.utcnow().strftime("%Y-%m-%d"),
            "priority": "0.3",
            "changefreq": "yearly",
        })

    urls = list({
        item["loc"]: item for item in urls
    }.values())

    urls.sort(key=lambda item: item["loc"])

    chunk_size = 45000
    chunks = [
        urls[i:i + chunk_size]
        for i in range(0, len(urls), chunk_size)
    ]

    if not chunks:
        chunks = [[]]

    for index, chunk in enumerate(chunks, start=1):
        entries = ""

        for item in chunk:
            entries += f"""
    <url>
        <loc>{html.escape(item['loc'])}</loc>
        <lastmod>{item['lastmod']}</lastmod>
        <changefreq>{item['changefreq']}</changefreq>
        <priority>{item['priority']}</priority>
    </url>"""

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""

        filename = "sitemap.xml" if index == 1 else f"sitemap-{index}.xml"

        write_file(
            os.path.join(OUTPUT_DIR, filename),
            xml
        )

    if len(chunks) > 1:
        sitemap_entries = ""

        for index in range(1, len(chunks) + 1):
            filename = (
                "sitemap.xml" if index == 1
                else f"sitemap-{index}.xml"
            )

            sitemap_entries += (
                f"<sitemap><loc>{html.escape(page_url(filename))}"
                f"</loc></sitemap>"
            )

        index_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_entries}
</sitemapindex>
"""

        write_file(
            os.path.join(OUTPUT_DIR, "sitemap-index.xml"),
            index_xml
        )

    xsl = r"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9"
exclude-result-prefixes="s">

<xsl:output method="html" encoding="UTF-8" indent="yes"/>

<xsl:template match="/">
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>XML Sitemap</title>
<style>
body {
    background:#0a0812;
    color:#f8f5ff;
    font-family:system-ui,sans-serif;
    padding:30px;
}
main {max-width:1100px;margin:auto;}
h1 {color:#f97316;}
p {color:#aaa0ba;}
table {
    width:100%;
    border-collapse:collapse;
    background:#171226;
    border-radius:12px;
    overflow:hidden;
}
th,td {
    padding:13px;
    text-align:left;
    border-bottom:1px solid #342a46;
}
th {color:#ec4899;}
a {color:#f97316;word-break:break-word;}
tr:hover {background:#211832;}
</style>
</head>
<body>
<main>
<h1>Spicy Party Games Sitemap</h1>
<p>Search engine index of published website URLs.</p>
<table>
<thead>
<tr>
<th>URL</th>
<th>Last Modified</th>
<th>Priority</th>
</tr>
</thead>
<tbody>
<xsl:for-each select="s:urlset/s:url">
<tr>
<td><a href="{s:loc}"><xsl:value-of select="s:loc"/></a></td>
<td><xsl:value-of select="s:lastmod"/></td>
<td><xsl:value-of select="s:priority"/></td>
</tr>
</xsl:for-each>
</tbody>
</table>
</main>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
"""

    write_file(
        os.path.join(OUTPUT_DIR, "sitemap.xsl"),
        xsl
    )

    robots = f"""User-agent: *
Allow: /

Sitemap: {page_url('sitemap.xml')}
"""

    write_file(
        os.path.join(OUTPUT_DIR, "robots.txt"),
        robots
    )


# ============================================================
# CLOUDflare / STATIC HOSTING SUPPORT
# ============================================================

def build_hosting_files():
    # Cloudflare Pages uses static files directly.
    # Avoid redirects or caching rules that could interfere with pages.

    headers = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Cache-Control: public, max-age=3600

/*.html
  Content-Type: text/html; charset=utf-8

/*.xml
  Content-Type: application/xml; charset=utf-8

/*.xsl
  Content-Type: text/xsl; charset=utf-8
"""

    write_file(
        os.path.join(OUTPUT_DIR, "_headers"),
        headers
    )

    # A simple static 404 page.
    body = """
    <main class="container">
        <section class="hero">
            <span class="eyebrow">404 • Card Not Found</span>
            <h1>Looks Like This Party <span class="gradient-text">Moved.</span></h1>
            <p class="lead">The requested page could not be found.</p>
            <a class="btn" href="/">Return to Homepage</a>
        </section>
    </main>
    """

    write_file(
        os.path.join(OUTPUT_DIR, "404.html"),
        document(
            "Page Not Found | " + SITE_NAME,
            "The requested party game page could not be found.",
            page_url("404.html"),
            body,
            include_age=False,
        )
    )


# ============================================================
# BUILD VALIDATION
# ============================================================

def validate_build(records):
    errors = []

    for record in records:
        path = os.path.join(
            OUTPUT_DIR,
            "deck",
            record["slug"] + ".html"
        )

        if not os.path.isfile(path):
            errors.append("Missing detail page: " + record["slug"])
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        required = [
            "application/ld+json",
            "RTA-5042-1996-1400-1577-RTA",
            "partyDeckData",
            "drawNext",
            "shuffleDeck",
            "pickPlayer",
            "party-edition",
            "Related Adult Party Games",
        ]

        for token in required:
            if token not in content:
                errors.append(
                    f"{record['slug']}: missing required element {token}"
                )

    for filename in [
        "index.html",
        "sitemap.xml",
        "sitemap.xsl",
        "robots.txt",
        "dmca.html",
        "2257.html",
    ]:
        if not os.path.isfile(os.path.join(OUTPUT_DIR, filename)):
            errors.append("Missing output file: " + filename)

    if errors:
        raise RuntimeError(
            "Build validation failed:\n" + "\n".join(errors)
        )


# ============================================================
# MAIN BUILD PIPELINE
# ============================================================

def main():
    print("=" * 65)
    print(f"{SITE_NAME} — Static pSEO Builder")
    print("=" * 65)

    print("\n[1/9] Reading CSV data...")
    records = load_csv()
    print(f"Loaded {len(records)} valid party decks.")

    print("\n[2/9] Preparing output directory...")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\n[3/9] Building category, topic and tag indexes...")
    categories, subcategories, tags = build_indexes(records)

    print(
        f"Found {len(categories)} categories, "
        f"{len(subcategories)} subcategories, "
        f"{len(tags)} unique tags."
    )

    print("\n[4/9] Generating homepage...")
    build_home(records, categories, subcategories, tags)

    print("\n[5/9] Generating interactive game detail pages...")
    for index, record in enumerate(records, start=1):
        build_detail(record, records)

        if index % 50 == 0 or index == len(records):
            print(f"Generated {index}/{len(records)} detail pages.")

    print("\n[6/9] Generating category pagination...")
    build_category_pages(categories)

    print("\n[7/9] Generating topic and tag hubs...")
    build_collection_pages(subcategories, tags)

    print("\n[8/9] Generating legal pages and hosting files...")
    build_legal_pages()
    build_hosting_files()

    print("\n[9/9] Generating XML sitemaps and validating output...")
    build_sitemaps(records, categories, subcategories, tags)
    validate_build(records)

    total_files = sum(
        len(files)
        for _, _, files in os.walk(OUTPUT_DIR)
    )

    print("\n" + "=" * 65)
    print("BUILD COMPLETED SUCCESSFULLY")
    print("=" * 65)
    print(f"Website:       {BASE_URL}")
    print(f"Output folder: {OUTPUT_DIR}/")
    print(f"Party decks:   {len(records)}")
    print(f"Categories:    {len(categories)}")
    print(f"Subcategories: {len(subcategories)}")
    print(f"Unique tags:   {len(tags)}")
    print(f"Generated:     {total_files} files")
    print("\nDeployment:")
    print("1. Upload the contents of dist/ to Cloudflare Pages.")
    print("2. Configure your custom domain or Workers route.")
    print("3. Submit /sitemap.xml to Google Search Console.")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\nBUILD ERROR:", str(error))
        raise
