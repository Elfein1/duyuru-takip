#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import os
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

KEYWORDS = {
    "spor": ["hakem", "görevlendirme", "toplantı", "mhgk", "mhk", "gözlemci"],
    "barolar": [], "universite": [], "saglik": [],
    "adalet": ["toplantı", "alım", "şart", "kadro", "başvuru", "ilan", "sınav"],
    "tayin": [], "toki": ["giresun", "samsun", "ordu"],
}

SITES = [
    ("Spor - TVF", "https://tvf.org.tr/icerikler/tvf-duyurular", "spor"),
    ("Spor - TVF MHGK", "https://tvf.org.tr/icerikler/mhgk-duyurular/", "spor"),
    ("Spor - Badminton", "https://www.badminton.org.tr/duyurular/", "spor"),
    ("Spor - TYF", "https://www.tyf.gov.tr/haberler/", "spor"),
    ("Spor - TYF Hakem", "https://www.tyf.gov.tr/hakem-islemleri/kurslar.html", "spor"),
    ("Spor - Masa Tenisi", "https://tmtf.gov.tr/duyurular", "spor"),
    ("Spor - Atletizm", "https://taf.org.tr/category/duyuru", "spor"),
    ("Spor - Bilardo MHK", "https://mhk.bilardo.gov.tr/", "spor"),
    ("Spor - Bilardo", "https://www.bilardo.org.tr/duyurular.html", "spor"),
    ("Spor - Ordu GSİM", "https://ordu.gsb.gov.tr/", "spor"),
    ("Giresun Barosu", "https://www.giresunbarosu.org.tr/Haberler", "barolar"),
    ("Ordu Barosu", "https://www.ordubarosu.org.tr/TumHaberler", "barolar"),
    ("Giresun Üniversitesi", "https://sbe.giresun.edu.tr/tr/news", "universite"),
    ("Sağlık - YHGM", "https://yhgm.saglik.gov.tr/TR-10084/duyurular.html", "saglik"),
    ("Sağlık - Giresun İSM", "https://giresunism.saglik.gov.tr/TR-22137/duyurular.html", "saglik"),
    ("Sağlık - SGB", "https://sgb.saglik.gov.tr/TR-59029/duyurular.html", "saglik"),
    ("Sağlık - SBSGM", "https://sbsgm.saglik.gov.tr/TR-1283/duyurular.html", "saglik"),
    ("Sağlık - KHGM", "https://khgm.saglik.gov.tr/TR-39978/duyurular.html", "saglik"),
    ("Bilirkişilik", "https://bilirkisilik.adalet.gov.tr/Home/TumHaberler/1", "adalet"),
    ("Trabzon BBK", "https://trabzonbbk.adalet.gov.tr/Arsiv/duyuru", "adalet"),
    ("Samsun BBK", "https://samsunbbk.adalet.gov.tr/Arsiv/duyuru", "adalet"),
    ("Bilirkişi Eğitim", "https://bilirkisilik.adalet.gov.tr/Home/SayfaDetay/egitim-kuruluslari02072020025435", "adalet"),
    ("YHGM Tayin", "https://yhgm.saglik.gov.tr/TR-34970/bolge-hizmet-gruplari.html", "tayin"),
    ("TOKİ Satış", "https://www.toki.gov.tr/satis/tr/duyurular", "toki"),
    ("TOKİ Haber", "https://www.toki.gov.tr/haberler", "toki"),
]

STATE_FILE = Path("tracker-state.json")


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_items(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = {}
    for link in soup.find_all("a", href=True):
        title = normalize(link.get_text(" ", strip=True))
        href = urljoin(base_url, link["href"])
        if len(title) < 8 or not href.startswith("http"):
            continue
        fingerprint = hashlib.sha256((title + "|" + href).encode("utf-8")).hexdigest()
        items[fingerprint] = {"title": title[:300], "url": href, "fingerprint": fingerprint}
    return list(items.values())[:100]


def send_discord(name, category, item, keywords):
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL bulunamadı; bildirim atlanıyor.")
        return
    found = [word for word in keywords if word.casefold() in item["title"].casefold()] if keywords else ["yeni duyuru"]
    payload = {"username": "Duyuru Takip", "embeds": [{
        "title": item["title"], "url": item["url"],
        "description": f"**Kaynak:** {name}\n**Kategori:** {category}\n**Anahtar kelime:** {', '.join(found)}",
        "color": 0xD98A00,
    }]}
    response = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    response.raise_for_status()


def main():
    state = json.loads(STATE_FILE.read_text("utf-8")) if STATE_FILE.exists() else {"seen": {}, "bootstrapped": False}
    seen = state.setdefault("seen", {})
    bootstrapped = state.get("bootstrapped", False)
    headers = {"User-Agent": "Duyuru-Takip-Botu/1.0 (GitHub Actions)"}

    for name, url, category in SITES:
        try:
            response = requests.get(url, headers=headers, timeout=25)
            response.raise_for_status()
            items = extract_items(response.text, url)
            old_seen = set(seen.get(name, []))

            for item in items:
                if item["fingerprint"] in old_seen:
                    continue
                keywords = KEYWORDS.get(category, [])
                matches = not keywords or any(word.casefold() in item["title"].casefold() for word in keywords)
                if bootstrapped and matches:
                    send_discord(name, category, item, keywords)

            seen[name] = list((set(seen.get(name, [])) | {x["fingerprint"] for x in items}))[:500]
            print(f"{name}: {len(items)} öğe tarandı")
        except Exception as exc:
            print(f"{name}: hata — {exc}")

    if not bootstrapped:
        state["bootstrapped"] = True
        print("İlk çalışma: mevcut duyurular bildirim vermeden kaydedildi.")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
