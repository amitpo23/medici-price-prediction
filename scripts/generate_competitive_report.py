#!/usr/bin/env python3
"""Generate Knowaa competitive scan report from existing JSON scan data."""

import json
import os
from datetime import datetime

SENTINEL = 1000  # Prices >= SENTINEL are sentinel/placeholder — excluded from ranking


def load_scan(path):
    with open(path) as f:
        return json.load(f)


def analyze_scan(data):
    """Classify hotels into sections A-E based on Knowaa competitiveness."""
    hotels = data['hotels']
    sec_a, sec_b, sec_c, sec_d, sec_e = [], [], [], [], []

    for h in hotels:
        offers = [o for o in h.get('offers', []) if o.get('price', 99999) < SENTINEL]

        if not offers:
            sec_e.append(h)
            continue

        knowaa_offers = [o for o in offers if o.get('provider') == 'Knowaa_Global_zenith']

        if not knowaa_offers:
            sec_d.append(h)
            continue

        knowaa_min = min(o['price'] for o in knowaa_offers)
        best_knowaa_offer = min(knowaa_offers, key=lambda x: x['price'])

        # Best price per provider
        prov_best = {}
        for o in offers:
            p = o['provider']
            if p not in prov_best or o['price'] < prov_best[p]['price']:
                prov_best[p] = o

        sorted_provs = sorted(prov_best.items(), key=lambda x: x[1]['price'])
        knowaa_rank = None
        for i, (prov, _) in enumerate(sorted_provs, 1):
            if prov == 'Knowaa_Global_zenith':
                knowaa_rank = i
                break

        cheapest_price = sorted_provs[0][1]['price']
        cheapest_prov = sorted_provs[0][0]
        second_price = sorted_provs[1][1]['price'] if len(sorted_provs) > 1 else None
        second_prov = sorted_provs[1][0] if len(sorted_provs) > 1 else None

        entry = {
            'hotelId': h['hotelId'],
            'venueId': h['venueId'],
            'name': h['name'],
            'knowaa_rank': knowaa_rank,
            'knowaa_price': knowaa_min,
            'knowaa_offer': best_knowaa_offer,
            'cheapest_price': cheapest_price,
            'cheapest_prov': cheapest_prov,
            'second_price': second_price,
            'second_prov': second_prov,
            'num_providers': len(prov_best),
            'sorted_provs': sorted_provs,
            'all_offers': offers,
            'raw': h,
        }

        if knowaa_rank == 1:
            sec_a.append(entry)
        elif knowaa_rank == 2:
            sec_b.append(entry)
        else:
            sec_c.append(entry)

    return sec_a, sec_b, sec_c, sec_d, sec_e


def make_lookup(sections):
    """Build (hotelId, venueId) -> section info dict."""
    lookup = {}
    letters = 'ABCDE'
    for letter, section in zip(letters, sections):
        for h in section:
            h_id = h.get('hotelId', h.get('name', '?'))
            v_id = h.get('venueId', h_id)
            key = (h_id, v_id)
            if letter in 'ABC':
                lookup[key] = {
                    'section': letter,
                    'rank': h.get('knowaa_rank'),
                    'price': h.get('knowaa_price'),
                }
            else:
                lookup[key] = {'section': letter}
    return lookup


def get_trend(hotel, prev_lk, cur_section):
    key = (hotel.get('hotelId', hotel.get('name', '?')),
           hotel.get('venueId', hotel.get('hotelId', '?')))
    prev = prev_lk.get(key)
    if not prev:
        return '⬆ New'
    ps = prev['section']
    sec_order = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}
    if ps == cur_section:
        return '→ Steady'
    if sec_order.get(cur_section, 9) < sec_order.get(ps, 9):
        return f'⬆ Was {ps}'
    else:
        return f'⬇ Was {ps}'


def fmt_gap_a(knowaa_price, second_price):
    """Section A: gap to 2nd cheapest (negative = we lead by this much)."""
    if second_price is None:
        return 'Only provider'
    gap = second_price - knowaa_price
    pct = (gap / knowaa_price * 100) if knowaa_price > 0 else 0
    return f'-${gap:.2f} (-{pct:.1f}%)'


def generate_report(cur_path, prev_path, out_base_name):
    cur = load_scan(cur_path)
    prev = load_scan(prev_path)

    cur_a, cur_b, cur_c, cur_d, cur_e = analyze_scan(cur)
    prev_a, prev_b, prev_c, prev_d, prev_e = analyze_scan(prev)

    prev_lookup = make_lookup((prev_a, prev_b, prev_c, prev_d, prev_e))

    total = len(cur['hotels'])
    a_count = len(cur_a)
    b_count = len(cur_b)
    c_count = len(cur_c)
    d_count = len(cur_d)
    e_count = len(cur_e)
    knowaa_total = a_count + b_count + c_count
    prev_knowaa = len(prev_a) + len(prev_b) + len(prev_c)
    prev_total = len(prev['hotels'])

    scan_date = cur['scanDate']
    scan_time = cur['scanTime']
    prev_date = prev['scanDate']
    prev_time = prev['scanTime']
    search_dates = cur.get('searchDates', {})
    date_window = f"{search_dates.get('checkIn', '?')} → {search_dates.get('checkOut', '?')}"

    # Name lookup across both scans
    name_lookup = {}
    for h in cur['hotels'] + prev['hotels']:
        name_lookup[(h['hotelId'], h['venueId'])] = h['name']

    # Which hotels gained/lost #1
    def get_ids(section):
        return {(h['hotelId'], h['venueId']) for h in section}

    prev_a_ids = get_ids(prev_a)
    cur_a_ids = get_ids(cur_a)
    lost_1st = prev_a_ids - cur_a_ids
    gained_1st = cur_a_ids - prev_a_ids

    def delta_str(a, b):
        d = a - b
        if d == 0:
            return '—'
        return f'**{d:+d}**'

    now = datetime.utcnow()

    lines = []
    lines.append("# Knowaa Competitive Scan Report")
    lines.append(f"**Date:** {scan_date} | **Time:** {scan_time} UTC")
    lines.append(f"**Search Window:** {date_window}")
    lines.append(f"**Previous Scan:** {prev_date} {prev_time} UTC")
    lines.append("**Source:** Innstant B2B Browser Scan (Refundable Only)")
    lines.append("**Provider Filter:** `Knowaa_Global_zenith`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    cur_label = f"{scan_date[5:]} {scan_time[:5]}"
    prev_label = f"{prev_date[5:]} {prev_time[:5]}"
    lines.append(f"| Metric | Today ({cur_label}) | Yesterday ({prev_label}) | Delta |")
    lines.append("|--------|---------------------|------------------------|-------|")
    lines.append(f"| Hotels scanned | {total} | {prev_total} | {delta_str(total, prev_total)} |")
    lines.append(f"| Knowaa #1 (cheapest) | **{a_count} ({a_count * 100 // total}%)** | {len(prev_a)} ({len(prev_a) * 100 // prev_total}%) | {delta_str(a_count, len(prev_a))} |")
    lines.append(f"| Knowaa #2 | {b_count} | {len(prev_b)} | {delta_str(b_count, len(prev_b))} |")
    lines.append(f"| Knowaa #3+ | {c_count} | {len(prev_c)} | {delta_str(c_count, len(prev_c))} |")
    lines.append(f"| Knowaa total presence | **{knowaa_total} ({knowaa_total * 100 // total}%)** | {prev_knowaa} ({prev_knowaa * 100 // prev_total}%) | {delta_str(knowaa_total, prev_knowaa)} |")
    lines.append(f"| No Knowaa (has offers) | {d_count} ({d_count * 100 // total}%) | {len(prev_d)} ({len(prev_d) * 100 // prev_total}%) | {delta_str(d_count, len(prev_d))} |")
    lines.append(f"| No refundable offers | {e_count} ({e_count * 100 // total}%) | {len(prev_e)} ({len(prev_e) * 100 // prev_total}%) | {delta_str(e_count, len(prev_e))} |")
    lines.append("")

    # Key alerts
    lines.append("### Key Alerts")
    lines.append("")

    if gained_1st:
        lines.append("**IMPROVED — New or recovered #1 positions:**")
        for k in sorted(gained_1st, key=lambda x: name_lookup.get(x, '')):
            name = name_lookup.get(k, str(k))
            was = prev_lookup.get(k, {}).get('section', 'not listed')
            h_data = next((h for h in cur_a if (h['hotelId'], h['venueId']) == k), None)
            if h_data:
                price = h_data['knowaa_price']
                cat = h_data['knowaa_offer'].get('category', '?')
                board = h_data['knowaa_offer'].get('board', '?')
                lines.append(f"- **{name}** — now #1 at **${price:.2f}** ({cat} {board}), was Section {was}")
        lines.append("")

    if lost_1st:
        lines.append("**DROPPED — Lost #1 position:**")
        for k in sorted(lost_1st, key=lambda x: name_lookup.get(x, '')):
            name = name_lookup.get(k, str(k))
            cur_sec = prev_lookup.get(k, {}).get('section', '?')
            # find current section
            cur_section_now = 'unknown'
            for sec_letter, sec_list in zip('BCDE', (cur_b, cur_c, cur_d, cur_e)):
                if any((h['hotelId'], h.get('venueId', h['hotelId'])) == k for h in sec_list):
                    cur_section_now = sec_letter
                    break
            lines.append(f"- **{name}** — now in Section {cur_section_now}")
        lines.append("")

    # Sentinel warning
    sentinel_in_a = [h for h in cur_a if h['knowaa_price'] >= SENTINEL]
    if sentinel_in_a:
        lines.append("**PRICING ALERT — Sentinel/placeholder prices in Section A:**")
        for h in sentinel_in_a:
            lines.append(f"- **{h['name']}** (venue {h['venueId']}) — Knowaa at **${h['knowaa_price']:.2f}** — needs rate review")
        lines.append("")

    # Section A overview stat
    real_prices_a = [h for h in cur_a if h['knowaa_price'] < SENTINEL]
    if real_prices_a:
        avg_price = sum(h['knowaa_price'] for h in real_prices_a) / len(real_prices_a)
        avg_gap = sum((h['second_price'] or h['knowaa_price']) - h['knowaa_price'] for h in real_prices_a) / len(real_prices_a)
        lines.append(f"**Section A stats (real prices only, n={len(real_prices_a)}):** avg Knowaa = ${avg_price:.2f}, avg lead over #2 = ${avg_gap:.2f}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── Section A ──────────────────────────────────────────────────
    lines.append(f"## Section A — Knowaa Is Cheapest (#1) — {a_count} hotel{'s' if a_count != 1 else ''}")
    lines.append("")
    if cur_a:
        lines.append("| Hotel | Venue | Cat | Board | Knowaa $ | 2nd $ | 2nd Provider | Gap | Trend |")
        lines.append("|-------|-------|-----|-------|----------|-------|-------------|-----|-------|")
        for h in sorted(cur_a, key=lambda x: x['knowaa_price']):
            cat = h['knowaa_offer'].get('category', '?')
            board = h['knowaa_offer'].get('board', '?')
            kp = h['knowaa_price']
            sp = h['second_price']
            sp_prov = h['second_prov'] or '—'
            gap = fmt_gap_a(kp, sp)
            trend = get_trend(h, prev_lookup, 'A')
            sp_str = f"${sp:.2f}" if sp is not None else '—'
            flag = ' ⚠️' if kp >= SENTINEL else ''
            lines.append(f"| {h['name']} | {h['venueId']} | {cat} | {board} | **${kp:.2f}**{flag} | {sp_str} | {sp_prov} | {gap} | {trend} |")
    else:
        lines.append("_No hotels where Knowaa is cheapest in this scan window._")
    lines.append("")

    # ── Section B ──────────────────────────────────────────────────
    lines.append(f"## Section B — Knowaa Is #2 — {b_count} hotel{'s' if b_count != 1 else ''}")
    lines.append("")
    if cur_b:
        lines.append("| Hotel | Venue | Cat | Board | Knowaa $ | Cheapest $ | Cheapest Provider | Gap | Trend |")
        lines.append("|-------|-------|-----|-------|----------|-----------|------------------|-----|-------|")
        for h in sorted(cur_b, key=lambda x: x['cheapest_price']):
            cat = h['knowaa_offer'].get('category', '?')
            board = h['knowaa_offer'].get('board', '?')
            kp = h['knowaa_price']
            cp = h['cheapest_price']
            cp_prov = h['cheapest_prov']
            gap = f"+${kp - cp:.2f} (+{(kp - cp) / cp * 100:.1f}%)" if cp > 0 else '—'
            trend = get_trend(h, prev_lookup, 'B')
            lines.append(f"| {h['name']} | {h['venueId']} | {cat} | {board} | ${kp:.2f} | **${cp:.2f}** | {cp_prov} | {gap} | {trend} |")
    else:
        lines.append("_No hotels where Knowaa is #2._")
    lines.append("")

    # ── Section C ──────────────────────────────────────────────────
    lines.append(f"## Section C — Knowaa Is #3 or Lower — {c_count} hotel{'s' if c_count != 1 else ''}")
    lines.append("")
    if cur_c:
        lines.append("| Hotel | Venue | Cat | Board | Our Price | Rank | Cheapest $ | Provider | Gap | Trend |")
        lines.append("|-------|-------|-----|-------|-----------|------|-----------|----------|-----|-------|")
        for h in sorted(cur_c, key=lambda x: x['knowaa_rank']):
            cat = h['knowaa_offer'].get('category', '?')
            board = h['knowaa_offer'].get('board', '?')
            kp = h['knowaa_price']
            cp = h['cheapest_price']
            cp_prov = h['cheapest_prov']
            rank = h['knowaa_rank']
            gap = f"+${kp - cp:.2f} (+{(kp - cp) / cp * 100:.1f}%)" if cp > 0 else '—'
            trend = get_trend(h, prev_lookup, 'C')
            lines.append(f"| {h['name']} | {h['venueId']} | {cat} | {board} | ${kp:.2f} | **#{rank}** | ${cp:.2f} | {cp_prov} | {gap} | {trend} |")
    else:
        lines.append("_No hotels where Knowaa is #3 or lower._")
    lines.append("")

    # ── Section D ──────────────────────────────────────────────────
    lines.append(f"## Section D — Has Offers but NO Knowaa — {d_count} hotels")
    lines.append("")
    lines.append("_Knowaa is not listed. These represent inventory gaps or distribution failures._")
    lines.append("")
    if cur_d:
        # Sort: previously in A/B/C first (priority warnings), then alphabetically
        prev_listed = []
        not_prev = []
        for h in cur_d:
            key = (h['hotelId'], h['venueId'])
            ps = prev_lookup.get(key, {}).get('section', '?')
            if ps in 'ABC':
                prev_listed.append((h, ps))
            else:
                not_prev.append(h)

        lines.append("| Hotel | Venue | Cheapest $ | Provider | Cat | Board | Trend |")
        lines.append("|-------|-------|-----------|----------|-----|-------|-------|")

        # Previously listed: always show
        for h, ps in sorted(prev_listed, key=lambda x: x[0].get('name', '')):
            offers = [o for o in h.get('offers', []) if o.get('price', 99999) < SENTINEL]
            if not offers:
                continue
            best = min(offers, key=lambda x: x['price'])
            trend = f"⬇ Was {ps}"
            lines.append(f"| {h['name']} | {h['venueId']} | **${best['price']:.2f}** | {best['provider']} | {best.get('category', '?')} | {best.get('board', '?')} | {trend} |")

        # Others: up to 25 alphabetically
        shown = len(prev_listed)
        for h in sorted(not_prev, key=lambda x: x.get('name', ''))[:25]:
            offers = [o for o in h.get('offers', []) if o.get('price', 99999) < SENTINEL]
            if not offers:
                continue
            best = min(offers, key=lambda x: x['price'])
            trend = get_trend(h, prev_lookup, 'D')
            lines.append(f"| {h['name']} | {h['venueId']} | ${best['price']:.2f} | {best['provider']} | {best.get('category', '?')} | {best.get('board', '?')} | {trend} |")
            shown += 1

        remaining = d_count - shown
        if remaining > 0:
            lines.append("")
            lines.append(f"> _{remaining} additional Section D hotels not shown — see full JSON for complete list._")
    lines.append("")

    # ── Section E ──────────────────────────────────────────────────
    lines.append(f"## Section E — No Refundable Offers — {e_count} hotels")
    lines.append("")
    lines.append("_These hotels returned no refundable offers in the scan window._")
    lines.append("")
    if cur_e:
        e_names = sorted(set(h['name'] for h in cur_e))
        for name in e_names[:25]:
            lines.append(f"- {name}")
        if len(e_names) > 25:
            lines.append(f"- _{len(e_names) - 25} more hotels — see JSON for full list_")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Scan Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Scan file | `{os.path.basename(cur_path)}` |")
    lines.append(f"| Scan timestamp | {scan_date} {scan_time} UTC |")
    lines.append(f"| Previous scan | {prev_date} {prev_time} UTC |")
    lines.append(f"| Hotels in scan | {total} |")
    lines.append(f"| Source | Innstant B2B (browser) |")
    lines.append(f"| Sentinel threshold | ${SENTINEL:,} (prices above excluded from ranking) |")
    lines.append(f"| Refundable only | Yes |")
    lines.append(f"| All room types | Yes (Standard, Deluxe, Superior, Suite, Apartment) |")
    lines.append(f"| All boards | Yes (RO + BB) |")
    lines.append("")
    lines.append(f"_Generated by Knowaa Competitive Scanner Agent — {now.strftime('%Y-%m-%d %H:%M')} UTC_")

    report = '\n'.join(lines)

    # Save
    for out_dir in [
        '/home/user/medici-price-prediction/scan-reports',
        '/home/user/medici-price-prediction/shared-reports',
    ]:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, out_base_name)
        with open(out_path, 'w') as f:
            f.write(report)
        print(f"Saved: {out_path}")

    return report


if __name__ == '__main__':
    CUR = '/home/user/medici-price-prediction/scan-reports/2026-04-13_05-48_full_scan.json'
    PREV = '/home/user/medici-price-prediction/scan-reports/2026-04-12_20-14_full_scan.json'
    FNAME = '2026-04-13_05-48_knowaa_competitive_report.md'
    report = generate_report(CUR, PREV, FNAME)
    print(f"\nReport length: {len(report)} chars")
