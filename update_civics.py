#!/usr/bin/env python3
"""
Automated Canadian Civic Leaders Live Sync Engine
Monitors Canadian first ministers and viceroys, updating provinces_data.json on GitHub CDN.
"""

import json
import re
import time
import urllib.request
import sys
from pathlib import Path

HEADERS = {
    'User-Agent': 'CitizenshipProCivicsBot/1.0 (https://eromteknas.com/citizenship-privacy/; contact: erom.teknas@gmail.com)'
}

PROVINCES_JSON_PATH = Path('provinces_data.json')

PROVINCE_NAMES = {
    'Ontario': 'ON',
    'Quebec': 'QC',
    'Nova Scotia': 'NS',
    'New Brunswick': 'NB',
    'Manitoba': 'MB',
    'British Columbia': 'BC',
    'Prince Edward Island': 'PE',
    'Saskatchewan': 'SK',
    'Alberta': 'AB',
    'Newfoundland and Labrador': 'NL',
    'Northwest Territories': 'NT',
    'Yukon': 'YT',
    'Nunavut': 'NU'
}

LG_PAGES = {
    'ON': 'Lieutenant_Governor_of_Ontario',
    'QC': 'Lieutenant_Governor_of_Quebec',
    'BC': 'Lieutenant_Governor_of_British_Columbia',
    'AB': 'Lieutenant_Governor_of_Alberta',
    'MB': 'Lieutenant_Governor_of_Manitoba',
    'SK': 'Lieutenant_Governor_of_Saskatchewan',
    'NS': 'Lieutenant_Governor_of_Nova_Scotia',
    'NB': 'Lieutenant_Governor_of_New_Brunswick',
    'NL': 'Lieutenant_Governor_of_Newfoundland_and_Labrador',
    'PE': 'Lieutenant_Governor_of_Prince_Edward_Island',
    'NT': 'Commissioner_of_the_Northwest_Territories',
    'YT': 'Commissioner_of_Yukon',
    'NU': 'Commissioner_of_Nunavut',
}

def clean_name(val):
    if not val:
        return None
    val = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', val)
    val = re.sub(r'\{\{[^}]*\}\}', '', val)
    val = re.sub(r'<ref[^>]*>.*?</ref>', '', val, flags=re.DOTALL)
    val = re.sub(r'<[^>]+>', '', val)
    val = val.replace('|', '').strip()
    val = re.sub(r'\s+', ' ', val).strip()
    return val if len(val) >= 2 else None

def fetch_first_ministers():
    url = 'https://en.wikipedia.org/w/api.php?action=parse&page=List_of_current_first_ministers_of_Canada&prop=wikitext&format=json'
    req = urllib.request.Request(url, headers=HEADERS)
    premiers = {}
    pm = None
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            wikitext = data['parse']['wikitext']['*']

        matches = re.findall(r'\{\{sortname\|([^|]+)\|([^}]+)\}\}.*?\|\s*\[\[([^\]|]+)', wikitext, re.DOTALL)
        for first, last, jur in matches:
            name = clean_name(f"{first} {last}")
            jur = jur.strip()
            if jur == 'Canada':
                pm = name
            elif jur in PROVINCE_NAMES and name:
                code = PROVINCE_NAMES[jur]
                premiers[code] = name
    except Exception as e:
        print(f"⚠️ Error fetching first ministers: {e}")
    return pm, premiers

def fetch_incumbent_from_page(page_title):
    url = f'https://en.wikipedia.org/w/api.php?action=parse&page={page_title}&prop=wikitext&section=0&format=json'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            wikitext = data['parse']['wikitext']['*']
            match = re.search(r'incumbent\s*=\s*([^\n<]+)', wikitext, re.IGNORECASE)
            if match:
                val = clean_name(match.group(1))
                if val and not val.startswith('{'):
                    return val
    except Exception as e:
        print(f"⚠️ Error fetching {page_title}: {e}")
    return None

def main():
    print("🇨🇦 Live Canadian Civics Sync Engine running...")
    if not PROVINCES_JSON_PATH.exists():
        print(f"❌ File not found: {PROVINCES_JSON_PATH}")
        sys.exit(1)

    with open(PROVINCES_JSON_PATH, 'r', encoding='utf-8') as f:
        provinces = json.load(f)

    pm, premiers = fetch_first_ministers()
    print(f"🏛️  Prime Minister: {pm}")
    print(f"🍁 Premiers verified: {len(premiers)}/13")

    changes = []
    
    # Check Premiers
    for p in provinces:
        pid = p['id']
        if pid in premiers:
            online_name = premiers[pid]
            current_name = p.get('premier')
            if online_name and current_name and online_name.lower() != current_name.lower():
                print(f"🔄 Premier update for {p['name']['en']} ({pid}): '{current_name}' -> '{online_name}'")
                changes.append({
                    'province': p['name']['en'],
                    'code': pid,
                    'role': 'Premier',
                    'old': current_name,
                    'new': online_name
                })
                p['premier'] = online_name

    # Check Lieutenant Governors
    for p in provinces:
        pid = p['id']
        page = LG_PAGES.get(pid)
        if page:
            time.sleep(0.3)
            online_lg = fetch_incumbent_from_page(page)
            current_lg = p.get('lieutenant_governor')
            if online_lg and current_lg and online_lg.lower() != current_lg.lower():
                print(f"🔄 Vice-Regal update for {p['name']['en']} ({pid}): '{current_lg}' -> '{online_lg}'")
                changes.append({
                    'province': p['name']['en'],
                    'code': pid,
                    'role': 'Lieutenant Governor / Commissioner',
                    'old': current_lg,
                    'new': online_lg
                })
                p['lieutenant_governor'] = online_lg

    if not changes:
        print("✅ Live roster is 100% up to date. No changes needed.")
        sys.exit(0)

    # Save updated provinces_data.json
    with open(PROVINCES_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(provinces, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved {len(changes)} update(s) to {PROVINCES_JSON_PATH}")

    # Generate Report
    report_lines = [
        "# 🇨🇦 Canadian Civic Leadership Auto-Sync Report",
        f"Updated automatically on {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n",
        "| Jurisdiction | Role | Previous Incumbent | Newly Verified Leader |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for c in changes:
        report_lines.append(f"| **{c['province']}** ({c['code']}) | {c['role']} | {c['old']} | **{c['new']}** |")

    with open('CIVICS_CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print("📄 Wrote CIVICS_CHANGELOG.md")
    sys.exit(0)

if __name__ == '__main__':
    main()
