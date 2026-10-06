#!/usr/bin/env python3
"""
Všichni hráči (domácí, pak hosté) ze zápisu o utkání na is.fotbal.cz.
Výpis: Příjmení, Jméno, FAČR ID, číslo dresu.

Příklady:
  python program.py <číslo utkání>
  python program.py <číslo utkání> --csv hraci.csv

Jak to funguje: hledání zápasů (prehled-zapasu.aspx) je chráněné CAPTCHA, proto
skript jde přes přehled soutěží (bez CAPTCHA). Číslo utkání má tvar
  RRRRSSSSSS KK ZZ
  = číslo soutěže, kolo, pořadí zápasu v kole.
Najde soutěž, projde zápisy v daném kole a vybere ten s odpovídajícím číslem.

Závislosti: pip install requests beautifulsoup4
"""
import argparse
import csv
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://is.fotbal.cz/public/"
COMP_SEARCH_URL = BASE + "souteze/prehled-soutezi.aspx?sport=fotbal"
REPORT_URL = BASE + "zapasy/zapis-o-utkani-report.aspx?sport=fotbal&zapas={}"
GUID_RE = re.compile(r"zapas=([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})")
CISLO_RE = re.compile(r"^(\d{4}\w{6})(\d{2})(\d{2})$")
HEADERS = {"User-Agent": "Mozilla/5.0 (facr_soupiska.py; osobni pouziti)"}


def form_payload(form):
    data = {}
    for inp in form.find_all("input"):
        if inp.get("name") and (inp.get("type") or "text").lower() == "hidden":
            data[inp["name"]] = inp.get("value", "")
    for sel in form.find_all("select"):
        if sel.get("name"):
            opt = sel.find("option", selected=True) or sel.find("option")
            data[sel["name"]] = opt.get("value", "") if opt else ""
    return data


# ---------- 1) číslo utkání -> odkaz na zápis ----------

def find_competition_url(session, comp_cislo):
    r = session.get(COMP_SEARCH_URL, timeout=30)
    r.raise_for_status()
    form = BeautifulSoup(r.text, "html.parser").find("form")
    data = form_payload(form)
    rocnik = form.find("select", id="listSearchRocnik")
    if rocnik:
        opt = rocnik.find("option", string=comp_cislo[:4])
        if opt:
            data[rocnik["name"]] = opt["value"]
    data["ctl00$MainContent$txtSearchCislo"] = comp_cislo
    data["__EVENTTARGET"] = "ctl00$MainContent$btnSearch"
    data["__EVENTARGUMENT"] = ""
    r = session.post(COMP_SEARCH_URL, data=data, timeout=30)
    r.raise_for_status()
    for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
        if "detail-souteze.aspx" in a["href"]:
            return urljoin(COMP_SEARCH_URL, a["href"])
    raise RuntimeError(f"Soutěž {comp_cislo} jsem nenašel.")


def round_match_guids(html, kolo):
    soup = BeautifulSoup(html, "html.parser")
    guids = []
    for table in soup.find_all("table"):
        if table.find("table"):
            continue
        head = table.find_previous(string=re.compile(r"\d+\.\s*kolo", re.I))
        if not head or int(re.search(r"\d+", head).group()) != kolo:
            continue
        for a in table.find_all("a", href=re.compile("zapis-o-utkani")):
            g = GUID_RE.search(a["href"]).group(1)
            if g not in guids:
                guids.append(g)
    return guids


def lookup_report_url(session, cislo):
    m = CISLO_RE.match(cislo)
    if not m:
        raise RuntimeError(f"Neočekávaný formát čísla utkání: {cislo}")
    comp, kolo, poradi = m.group(1), int(m.group(2)), int(m.group(3))
    comp_url = find_competition_url(session, comp)
    r = session.get(comp_url, timeout=30)
    r.raise_for_status()
    guids = round_match_guids(r.text, kolo)
    if not guids:
        raise RuntimeError(f"V soutěži {comp} jsem nenašel {kolo}. kolo.")
    # nejdřív zkus zápas na pozici podle čísla, pak ostatní
    order = guids[poradi - 1:poradi] + guids
    for g in dict.fromkeys(order):
        url = REPORT_URL.format(g)
        r = session.get(url, timeout=30)
        if cislo in r.text:
            return url, r.text
    raise RuntimeError(f"V {kolo}. kole jsem nenašel zápis s číslem {cislo}.")


# ---------- 2) zápis -> hráči ----------

def parse_players(html):
    soup = BeautifulSoup(html, "html.parser")
    teams = {}
    for side in ("Domácí", "Hosté"):
        el = soup.find(string=re.compile(rf"^\s*{side}\s*$"))
        nxt = el.find_next(string=re.compile(r"\S")) if el else None
        teams[side] = re.sub(r"^\S+\s+-\s+", "", nxt.strip()) if nxt else side

    groups = []
    for side, key in (("Domácí", "Hráči domácí"), ("Hosté", "Hráči hosté")):
        h = soup.find(string=re.compile(key))
        if not h:
            continue
        players = []
        for tr in h.find_next("table").find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            div = tds[1].find("div") or tds[1]
            cele = (div.find(string=True, recursive=False) or "").strip()
            # IS uvádí "Příjmení Jméno"; víceslovné bývá příjmení
            prijmeni, _, jmeno = cele.rpartition(" ")
            players.append({
                "prijmeni": prijmeni or jmeno,
                "jmeno": jmeno if prijmeni else "",
                "id": tds[2].get_text(" ", strip=True).split(",")[0].strip(),
                "dres": tds[0].get_text(strip=True),
            })
        groups.append((side, teams[side], players))
    return groups


# ---------- main ----------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("cislo", help="číslo utkání (14 znaků, viz README)")
    ap.add_argument("--csv", help="výstup do CSV")
    args = ap.parse_args()

    s = requests.Session()
    s.headers.update(HEADERS)

    report_url, html = lookup_report_url(s, args.cislo)
    print(f"Zápis: {report_url}", file=sys.stderr)
    groups = parse_players(html)
    if not any(p for _, _, p in groups):
        sys.exit("V zápisu jsem nenašel žádné hráče (změnila se struktura stránky?).")

    rows = []
    for side, team, players in groups:
        print(f"\n== {side}: {team} ==")
        print(f"{'Příjmení':<22} {'Jméno':<14} {'FAČR ID':<9} {'Dres':>4}")
        for p in players:
            print(f"{p['prijmeni']:<22} {p['jmeno']:<14} {p['id']:<9} {p['dres']:>4}")
            rows.append({"strana": side, "tym": team, **p})

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["strana", "tym", "prijmeni", "jmeno", "id", "dres"])
            w.writeheader()
            w.writerows(rows)
        print(f"\nUloženo do {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
