#!/usr/bin/env python3
"""Convert vulnerability-lifecycle-comparison.md to Confluence storage format and publish."""

import json
import re
import sys
import urllib.request
import base64

CONFLUENCE_URL = "https://datadoghq.atlassian.net/wiki"
USERNAME = "eoghan.mellott@datadoghq.com"
API_TOKEN = "ATATT3xFfGF0BOxGAQQCbDOb0s_V62X6qwUiAQhh0BTlLrKeEYSq3ZsVYK8sUva5CBjOVXPGBc4-sJLWefoaBt17TG8pAd8T388ssHjvrXK0GfttGUzsxSryew_LKDAa6XYQbfQ6PImQDkzxsqiWOdODuA4wbQEcxvnOAFmmA0CJKlAvKbBZ8M8=3A46B0FF"
SPACE_KEY = "~6232430366b6de006887bc22"


def md_inline(text):
    """Convert inline markdown (bold, links, code) to Confluence storage HTML."""
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text


def md_to_confluence(md_text):
    """Convert markdown to Confluence storage format XHTML."""
    lines = md_text.split('\n')
    html_parts = []
    i = 0
    in_list = False
    in_table = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            i += 1
            continue

        if stripped.startswith('# ') and not stripped.startswith('## '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            html_parts.append(f'<h1>{md_inline(stripped[2:])}</h1>')
            i += 1
            continue

        if stripped.startswith('## ') and not stripped.startswith('### '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            html_parts.append(f'<h2>{md_inline(stripped[3:])}</h2>')
            i += 1
            continue

        if stripped.startswith('### ') and not stripped.startswith('#### '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            html_parts.append(f'<h3>{md_inline(stripped[4:])}</h3>')
            i += 1
            continue

        if stripped.startswith('#### '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            html_parts.append(f'<h4>{md_inline(stripped[5:])}</h4>')
            i += 1
            continue

        if stripped.startswith('> '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            panel_content = []
            while i < len(lines) and lines[i].strip().startswith('> '):
                panel_content.append(md_inline(lines[i].strip()[2:]))
                i += 1
            html_parts.append(
                '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
                + '<br/>'.join(panel_content)
                + '</ac:rich-text-body></ac:structured-macro>'
            )
            continue

        if stripped.startswith('---'):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            html_parts.append('<hr/>')
            i += 1
            continue

        if stripped.startswith('- '):
            if in_table:
                html_parts.append('</tbody></table>')
                in_table = False
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append(f'<li>{md_inline(stripped[2:])}</li>')
            i += 1
            continue

        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]

            if all(re.match(r'^[-:]+$', c) for c in cells):
                i += 1
                continue

            if not in_table:
                in_table = True
                header_cells = ''.join(f'<th><p>{md_inline(c)}</p></th>' for c in cells)
                html_parts.append(
                    '<table><thead><tr>' + header_cells + '</tr></thead><tbody>'
                )
                i += 1
                continue

            row_cells = ''.join(f'<td><p>{md_inline(c)}</p></td>' for c in cells)
            html_parts.append('<tr>' + row_cells + '</tr>')
            i += 1
            continue

        if in_list:
            html_parts.append('</ul>')
            in_list = False
        if in_table:
            html_parts.append('</tbody></table>')
            in_table = False

        html_parts.append(f'<p>{md_inline(stripped)}</p>')
        i += 1

    if in_list:
        html_parts.append('</ul>')
    if in_table:
        html_parts.append('</tbody></table>')

    return '\n'.join(html_parts)


def create_page(title, body_html, space_key):
    """Create a Confluence page via REST API v1."""
    url = f"{CONFLUENCE_URL}/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": body_html,
                "representation": "storage"
            }
        }
    }

    data = json.dumps(payload).encode('utf-8')
    credentials = base64.b64encode(f"{USERNAME}:{API_TOKEN}".encode()).decode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {credentials}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            page_id = result["id"]
            page_url = f"{CONFLUENCE_URL}{result['_links']['webui']}"
            print(f"Page created successfully!")
            print(f"  ID: {page_id}")
            print(f"  URL: {page_url}")
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def main():
    md_path = "vulnerability-lifecycle-comparison.md"
    with open(md_path, 'r') as f:
        md_content = f.read()

    html_body = md_to_confluence(md_content)
    title = "Vulnerability / Finding / Signal Lifecycle Comparison"

    print(f"Creating page: '{title}'")
    print(f"Space: {SPACE_KEY}")
    print(f"Content length: {len(html_body)} chars")
    print()

    create_page(title, html_body, SPACE_KEY)


if __name__ == "__main__":
    main()
