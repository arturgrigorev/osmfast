#!/usr/bin/env python3
"""Generate HTML documentation from JSON command docs."""

import json
import subprocess
import sys
from pathlib import Path
from html import escape

DOCS_DIR = Path("osm_core/cli/docs")
OUTPUT_DIR = Path("docs/commands")

# Command categories for navigation
CATEGORIES = {
    "Data Extraction": ["extract", "filter", "convert", "merge", "clip", "split", "sample", "head"],
    "Feature Extraction": [
        "poi", "buildings", "roads", "amenity", "shop", "food", "healthcare", "education",
        "tourism", "leisure", "natural", "water", "landuse", "trees", "parking",
        "transit", "railway", "power", "historic", "emergency", "barrier", "boundary", "address"
    ],
    "Routing & Navigation": [
        "route", "route-multi", "directions", "isochrone", "alternatives",
        "distance-matrix", "nearest-road", "nearest", "catchment"
    ],
    "Network Analysis": [
        "network", "connectivity", "centrality", "bottleneck", "detour-factor",
        "walkability", "bikeability"
    ],
    "Spatial Operations": [
        "bbox", "within", "buffer", "centroid", "densify", "simplify"
    ],
    "Data Analysis": [
        "stats", "count", "tags", "unique", "names", "surface", "info"
    ],
    "Data Manipulation": [
        "sort", "join", "lookup", "search"
    ],
    "Visualization": [
        "render", "render-walkability"
    ],
    "Utility": [
        "help", "version", "gui"
    ]
}

# Reverse lookup: command -> category
def get_category(cmd_name):
    for cat, cmds in CATEGORIES.items():
        if cmd_name in cmds:
            return cat
    return "Other"

# HTML template
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>osmfast {cmd_name} | OSMFast Documentation</title>
    <style>
:root {{
    --red-dark: #c74634;
    --red: #f80000;
    --red-light: #ff6b6b;
    --black: #1a1a1a;
    --gray-dark: #312d2a;
    --gray: #6b6b6b;
    --gray-light: #e8e8e8;
    --white: #ffffff;
    --bg: #f5f5f5;
    --link: #0066cc;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Oracle Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--black);
    line-height: 1.5;
    font-size: 14px;
}}

.container {{
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 24px;
}}

.page-header {{
    background: var(--black);
    color: var(--white);
    border-bottom: 4px solid var(--red);
    padding: 24px 0;
}}

.breadcrumb {{
    font-size: 13px;
    margin-bottom: 16px;
}}

.breadcrumb a {{
    color: var(--gray-light);
    text-decoration: none;
}}

.breadcrumb a:hover {{
    color: var(--white);
}}

.breadcrumb span {{
    color: var(--gray-light);
    margin: 0 8px;
}}

.page-header h1 {{
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 28px;
    font-weight: 400;
    margin-bottom: 8px;
}}

.page-header h1 .prefix {{
    color: var(--gray-light);
}}

.page-header .desc {{
    color: var(--gray-light);
    font-size: 15px;
}}

main {{
    padding: 32px 0;
}}

.back-link {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--link);
    text-decoration: none;
    font-size: 13px;
    margin-bottom: 24px;
}}

.back-link:hover {{
    text-decoration: underline;
}}

.content-section {{
    background: var(--white);
    border: 1px solid var(--gray-light);
    border-radius: 4px;
    margin-bottom: 24px;
}}

.section-header {{
    background: var(--white);
    padding: 14px 20px;
    border-bottom: 2px solid var(--red);
    font-weight: 700;
    font-size: 13px;
    color: var(--black);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.section-body {{
    padding: 20px;
}}

.overview-section p {{
    font-size: 14px;
    line-height: 1.7;
    color: var(--gray-dark);
    white-space: pre-wrap;
}}

.overview-section code {{
    background: var(--bg);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
    color: var(--red-dark);
}}

pre {{
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px 20px;
    border-radius: 4px;
    overflow-x: auto;
    font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace;
    font-size: 13px;
    line-height: 1.6;
}}

.example-block {{
    margin-bottom: 16px;
}}

.example-block:last-child {{
    margin-bottom: 0;
}}

.example-label {{
    font-size: 12px;
    color: var(--gray);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.example-code {{
    background: var(--bg);
    border: 1px solid var(--gray-light);
    padding: 12px 16px;
    border-radius: 4px;
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 13px;
    color: var(--black);
}}

.options-table {{
    width: 100%;
    border-collapse: collapse;
}}

.options-table th, .options-table td {{
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--gray-light);
}}

.options-table th {{
    background: var(--bg);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.options-table td:first-child {{
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 13px;
    color: var(--red-dark);
    white-space: nowrap;
}}

.related-links {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.related-link {{
    display: inline-block;
    padding: 6px 12px;
    background: var(--bg);
    border: 1px solid var(--gray-light);
    border-radius: 4px;
    color: var(--link);
    text-decoration: none;
    font-size: 13px;
}}

.related-link:hover {{
    border-color: var(--red);
    background: var(--white);
}}

footer {{
    background: var(--black);
    color: var(--gray-light);
    padding: 32px 0;
    margin-top: 48px;
}}

footer .container {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

footer a {{
    color: var(--gray-light);
    text-decoration: none;
}}

footer a:hover {{
    color: var(--white);
}}

@media (max-width: 768px) {{
    footer .container {{
        flex-direction: column;
        gap: 16px;
        text-align: center;
    }}
}}
</style>
</head>
<body>
    <div class="page-header">
        <div class="container">
            <div class="breadcrumb">
                <a href="../index.html">Documentation</a>
                <span>/</span>
                <a href="../index.html#{category_anchor}">{category}</a>
                <span>/</span>
                {cmd_name}
            </div>
            <h1><span class="prefix">osmfast</span> {cmd_name}</h1>
            <p class="desc">{summary}</p>
        </div>
    </div>

    <main>
        <div class="container">
            <a href="../index.html" class="back-link">
                <span>&larr;</span> Back to Documentation
            </a>

            <div class="content-section overview-section">
                <div class="section-header">Description</div>
                <div class="section-body">
                    <p>{description}</p>
                </div>
            </div>

            {usage_section}

            {examples_section}

            {options_section}

            {output_section}

            {related_section}
        </div>
    </main>

    <footer>
        <div class="container">
            <div>OSMFast Documentation</div>
            <div>
                <a href="https://github.com/anthropics/osmfast">GitHub</a>
            </div>
        </div>
    </footer>
</body>
</html>
'''


def generate_usage_section(usage_list):
    """Generate usage section HTML."""
    if not usage_list:
        return ""

    usage_html = "\n".join(f"<div>{escape(u)}</div>" for u in usage_list)
    return f'''
            <div class="content-section">
                <div class="section-header">Usage</div>
                <div class="section-body">
                    <pre>{escape(chr(10).join(usage_list))}</pre>
                </div>
            </div>'''


def generate_examples_section(examples):
    """Generate examples section HTML."""
    if not examples:
        return ""

    blocks = []
    for title, cmd in examples:
        blocks.append(f'''
        <div class="example-block">
            <div class="example-label">{escape(title)}</div>
            <div class="example-code">{escape(cmd)}</div>
        </div>''')

    return f'''
            <div class="content-section">
                <div class="section-header">Examples</div>
                <div class="section-body">
                    {"".join(blocks)}
                </div>
            </div>'''


def generate_options_section(options):
    """Generate options section HTML."""
    if not options:
        return ""

    rows = []
    for opt, desc in options.items():
        rows.append(f'''
                        <tr>
                            <td>{escape(opt)}</td>
                            <td>{escape(desc)}</td>
                        </tr>''')

    return f'''
            <div class="content-section">
                <div class="section-header">Options</div>
                <div class="section-body">
                    <table class="options-table">
                        <thead>
                            <tr>
                                <th>Option</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody>{"".join(rows)}
                        </tbody>
                    </table>
                </div>
            </div>'''


def generate_output_section(output):
    """Generate output section HTML."""
    if not output:
        return ""

    return f'''
            <div class="content-section">
                <div class="section-header">Output</div>
                <div class="section-body">
                    <p style="white-space: pre-wrap;">{escape(output)}</p>
                </div>
            </div>'''


def generate_related_section(related):
    """Generate related commands section HTML."""
    if not related:
        return ""

    links = []
    for cmd in related:
        links.append(f'<a href="{cmd}.html" class="related-link">{cmd}</a>')

    return f'''
            <div class="content-section">
                <div class="section-header">Related Commands</div>
                <div class="section-body">
                    <div class="related-links">
                        {"".join(links)}
                    </div>
                </div>
            </div>'''


def generate_html(doc):
    """Generate HTML from a documentation dict."""
    cmd_name = doc.get("name", "unknown")
    category = get_category(cmd_name)
    category_anchor = category.lower().replace(" ", "-").replace("&", "")

    html = HTML_TEMPLATE.format(
        cmd_name=cmd_name,
        category=category,
        category_anchor=category_anchor,
        summary=escape(doc.get("summary", "")),
        description=escape(doc.get("description", "")),
        usage_section=generate_usage_section(doc.get("usage", [])),
        examples_section=generate_examples_section(doc.get("examples", [])),
        options_section=generate_options_section(doc.get("options", {})),
        output_section=generate_output_section(doc.get("output", "")),
        related_section=generate_related_section(doc.get("related", []))
    )

    return html


def main():
    """Generate HTML documentation from JSON files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    errors = 0

    for json_file in sorted(DOCS_DIR.glob("*.json")):
        if json_file.name.startswith("_"):
            continue

        try:
            doc = json.loads(json_file.read_text(encoding="utf-8"))
            cmd_name = doc.get("name", json_file.stem)

            html = generate_html(doc)

            output_file = OUTPUT_DIR / f"{cmd_name}.html"
            output_file.write_text(html, encoding="utf-8")

            generated += 1
            print(f"  Generated: {cmd_name}.html")

        except Exception as e:
            errors += 1
            print(f"  Error processing {json_file.name}: {e}")

    print()
    print(f"Generated {generated} HTML files in {OUTPUT_DIR}")
    if errors:
        print(f"Errors: {errors}")

    return errors


def generate_index_html():
    """Generate the main index.html with all commands."""

    # Load all docs
    docs = {}
    for json_file in sorted(DOCS_DIR.glob("*.json")):
        if json_file.name.startswith("_"):
            continue
        try:
            doc = json.loads(json_file.read_text(encoding="utf-8"))
            docs[doc.get("name", json_file.stem)] = doc
        except Exception:
            pass

    # Build category sections
    category_sections = []
    for category, cmds in CATEGORIES.items():
        category_id = category.lower().replace(" ", "-").replace("&", "")

        # Get commands that exist in docs
        existing_cmds = [(cmd, docs.get(cmd)) for cmd in cmds if cmd in docs]
        if not existing_cmds:
            continue

        cards = []
        for cmd_name, doc in existing_cmds:
            if doc:
                summary = escape(doc.get("summary", ""))
                cards.append(f'''
                <a href="commands/{cmd_name}.html" class="command-card">
                    <div class="command-name">{cmd_name}</div>
                    <div class="command-desc">{summary}</div>
                </a>''')

        category_sections.append(f'''
        <div class="category" id="{category_id}">
            <div class="category-header">
                <h2>{category}</h2>
                <span class="category-count">{len(existing_cmds)} commands</span>
            </div>
            <div class="commands-grid">
                {"".join(cards)}
            </div>
        </div>''')

    # Build navigation links
    nav_links = []
    for category in CATEGORIES.keys():
        category_id = category.lower().replace(" ", "-").replace("&", "")
        nav_links.append(f'<a href="#{category_id}">{category}</a>')

    total_commands = len(docs)

    index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OSMFast Documentation</title>
    <style>
:root {{
    --red-dark: #c74634;
    --red: #f80000;
    --red-light: #ff6b6b;
    --black: #1a1a1a;
    --gray-dark: #312d2a;
    --gray: #6b6b6b;
    --gray-light: #e8e8e8;
    --white: #ffffff;
    --bg: #f5f5f5;
    --link: #0066cc;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Oracle Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--black);
    line-height: 1.5;
    font-size: 14px;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 24px;
}}

header {{
    background: var(--black);
    color: var(--white);
    border-bottom: 4px solid var(--red);
}}

.header-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid var(--gray-dark);
}}

.logo {{
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
    color: var(--white);
}}

.logo-icon {{
    width: 36px;
    height: 36px;
    background: var(--red);
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 18px;
}}

.logo-text {{
    font-size: 20px;
    font-weight: 600;
    letter-spacing: -0.5px;
}}

.header-links {{
    display: flex;
    gap: 24px;
}}

.header-links a {{
    color: var(--gray-light);
    text-decoration: none;
    font-size: 13px;
}}

.header-links a:hover {{
    color: var(--white);
}}

.header-main {{
    padding: 32px 0;
}}

.header-main h1 {{
    font-size: 32px;
    font-weight: 300;
    margin-bottom: 8px;
}}

.header-main p {{
    color: var(--gray-light);
    font-size: 16px;
}}

.stats-bar {{
    background: var(--gray-dark);
    padding: 16px 0;
}}

.stats-grid {{
    display: flex;
    gap: 48px;
}}

.stat-item {{
    text-align: center;
}}

.stat-value {{
    font-size: 28px;
    font-weight: 600;
    color: var(--white);
}}

.stat-label {{
    font-size: 12px;
    color: var(--white);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    opacity: 0.85;
}}

nav {{
    background: var(--white);
    border-bottom: 1px solid var(--gray-light);
    position: sticky;
    top: 0;
    z-index: 100;
    padding: 12px 0;
}}

nav .container {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}

nav a {{
    display: block;
    padding: 8px 14px;
    color: var(--black);
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid var(--gray-light);
    border-radius: 4px;
    transition: all 0.15s;
}}

nav a:hover {{
    color: var(--red-dark);
    border-color: var(--red);
    background: var(--bg);
}}

.search-box {{
    flex: 1;
    max-width: 300px;
    margin-left: auto;
}}

.search-input {{
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--gray-light);
    border-radius: 4px;
    font-size: 13px;
}}

.search-input:focus {{
    outline: none;
    border-color: var(--red);
}}

.command-card.hidden {{
    display: none;
}}

.category.hidden {{
    display: none;
}}

.no-results {{
    text-align: center;
    padding: 40px;
    color: var(--gray);
    display: none;
}}

main {{
    padding: 32px 0;
}}

.category {{
    margin-bottom: 48px;
}}

.category-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--gray-light);
}}

.category-header h2 {{
    font-size: 20px;
    font-weight: 600;
    color: var(--black);
}}

.category-count {{
    background: var(--gray-light);
    color: var(--gray);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}}

.commands-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}}

.command-card {{
    background: var(--white);
    border: 1px solid var(--gray-light);
    border-radius: 4px;
    padding: 20px;
    text-decoration: none;
    color: inherit;
    transition: all 0.15s;
    display: block;
}}

.command-card:hover {{
    border-color: var(--red);
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}}

.command-name {{
    font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace;
    font-size: 15px;
    font-weight: 600;
    color: var(--red-dark);
    margin-bottom: 6px;
}}

.command-desc {{
    color: var(--gray);
    font-size: 13px;
    line-height: 1.4;
}}

footer {{
    background: var(--black);
    color: var(--gray-light);
    padding: 32px 0;
    margin-top: 48px;
}}

footer .container {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

footer a {{
    color: var(--gray-light);
    text-decoration: none;
}}

footer a:hover {{
    color: var(--white);
}}

@media (max-width: 768px) {{
    .header-top {{
        flex-direction: column;
        gap: 12px;
    }}
    .stats-grid {{
        flex-wrap: wrap;
        gap: 24px;
    }}
    nav .container {{
        overflow-x: auto;
    }}
    .commands-grid {{
        grid-template-columns: 1fr;
    }}
    footer .container {{
        flex-direction: column;
        gap: 16px;
        text-align: center;
    }}
}}
</style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-top">
                <a href="index.html" class="logo">
                    <div class="logo-icon">O</div>
                    <span class="logo-text">OSMFast</span>
                </a>
                <div class="header-links">
                    <a href="getting-started.html">Getting Started</a>
                    <a href="https://github.com/anthropics/osmfast">GitHub</a>
                </div>
            </div>
            <div class="header-main">
                <h1>Command Reference</h1>
                <p>Complete documentation for all OSMFast commands</p>
            </div>
        </div>
        <div class="stats-bar">
            <div class="container">
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{total_commands}</div>
                        <div class="stat-label">Commands</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(CATEGORIES)}</div>
                        <div class="stat-label">Categories</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">7,000+</div>
                        <div class="stat-label">Features/sec</div>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <nav>
        <div class="container">
            {"".join(nav_links)}
            <div class="search-box">
                <input type="text" class="search-input" id="searchInput" placeholder="Search commands..." autocomplete="off">
            </div>
        </div>
    </nav>

    <main>
        <div class="container">
            {"".join(category_sections)}
            <div class="no-results" id="noResults">No commands found matching your search.</div>
        </div>
    </main>

    <script>
    document.getElementById('searchInput').addEventListener('input', function(e) {{
        const query = e.target.value.toLowerCase().trim();
        const cards = document.querySelectorAll('.command-card');
        const categories = document.querySelectorAll('.category');
        const noResults = document.getElementById('noResults');
        let hasResults = false;

        cards.forEach(card => {{
            const name = card.querySelector('.command-name').textContent.toLowerCase();
            const desc = card.querySelector('.command-desc').textContent.toLowerCase();
            const matches = query === '' || name.includes(query) || desc.includes(query);
            card.classList.toggle('hidden', !matches);
            if (matches) hasResults = true;
        }});

        // Hide empty categories
        categories.forEach(cat => {{
            const visibleCards = cat.querySelectorAll('.command-card:not(.hidden)');
            cat.classList.toggle('hidden', visibleCards.length === 0);
        }});

        noResults.style.display = (query && !hasResults) ? 'block' : 'none';
    }});
    </script>

    <footer>
        <div class="container">
            <div>OSMFast Documentation - Generated from JSON</div>
            <div>
                <a href="https://github.com/anthropics/osmfast">GitHub</a>
            </div>
        </div>
    </footer>
</body>
</html>
'''

    output_file = Path("docs/index.html")
    output_file.write_text(index_html, encoding="utf-8")
    print(f"Generated: {output_file}")


if __name__ == "__main__":
    errors = main()
    generate_index_html()
    sys.exit(errors)
