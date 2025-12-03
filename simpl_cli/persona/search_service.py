#!/usr/bin/env python3

import hashlib
import pickle
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup
from faker import Faker

from ..ui.highlighter import create_console

console = create_console()
faker = Faker()

CACHE_DIR = Path.home() / ".cache" / "simple_cli" / "search"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROXIES_LIST = [
    "142.111.48.253:7030:initditer89:initditer89",
    "198.23.239.134:6540:initditer89:initditer89",
    "45.38.107.97:6014:initditer89:initditer89",
    "107.172.163.27:6543:initditer89:initditer89",
    "64.137.96.74:6641:initditer89:initditer89",
    "154.203.43.247:5536:initditer89:initditer89",
    "84.247.60.125:6095:initditer89:initditer89",
    "216.10.27.159:6837:initditer89:initditer89",
    "142.111.67.146:5611:initditer89:initditer89",
    "142.147.128.93:6593:initditer89:initditer89",
]


def _generate_headers() -> Dict[str, str]:
    return {
        "User-Agent": faker.user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9,id-ID;q=0.8",
        "X-Forwarded-For": faker.ipv4_public(),
        "Connection": "keep-alive",
    }


def _get_random_proxy() -> Dict[str, str]:
    proxy = random.choice(PROXIES_LIST)
    ip, port, username, password = proxy.split(":")
    proxy_url = f"http://{username}:{password}@{ip}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.pkl"


def _load_cache(key: str) -> Optional[Dict]:
    path = _cache_path(key)
    if not path.exists():
        return None

    try:
        with path.open("rb") as handle:
            cached = pickle.load(handle)

        fetched_at = cached.get("searchParameters", {}).get("fetched_at")
        if fetched_at:
            fetched_dt = datetime.fromisoformat(fetched_at)
            if (datetime.now() - fetched_dt).total_seconds() <= 86400:
                console.log(f"Using cached search result: [cyan]{path.name}[/cyan]")
                return cached
    except Exception as error:  
        console.log(f"[red]Failed to load cache:[/red] {error}")

    return None


def _save_cache(key: str, data: Dict) -> None:
    path = _cache_path(key)
    payload = data.copy()
    payload.setdefault("searchParameters", {})
    payload["searchParameters"]["fetched_at"] = datetime.now().isoformat()

    try:
        with path.open("wb") as handle:
            pickle.dump(payload, handle)
        console.log(f"Saved search cache: [dim]{path}[/dim]")
    except Exception as error:  
        console.log(f"[red]Failed to save cache:[/red] {error}")


def _clean_text(text: str) -> str:
    return " ".join(text.split()) if text else ""


def _fetch(url: str, headers: Dict[str, str], proxies: Optional[Dict[str, str]]) -> requests.Response:
    response = requests.get(
        url,
        headers=headers,
        proxies=proxies,
        timeout=15.0,
        allow_redirects=True,
    )
    response.raise_for_status()
    console.log(f":link: Fetched [link={url}]{url}[/link]")
    return response


def brave_search(query: str, limit: int = 12, filter_domain: Optional[str] = None) -> Dict:
    if cached := _load_cache(query):
        return cached

    headers = _generate_headers()
    url = f"https://search.brave.com/search?q={requests.utils.quote(query)}"
    start = time.time()
    proxies = _get_random_proxy()

    try:
        response = _fetch(url, headers, proxies)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as error:  
        console.log(f"[red]Search fetch failed:[/red] {error}")
        return {
            "status": "error",
            "message": str(error),
            "searchParameters": {
                "query": query,
                "engine": "brave",
                "type": "search",
                "fetched_at": datetime.now().isoformat(),
                "latency_ms": int((time.time() - start) * 1000),
            },
            "organic_results": [],
            "debug": {
                "user_agent": headers.get("User-Agent"),
                "ip": headers.get("X-Forwarded-For"),
                "result_count": 0,
            },
        }

    organic_results = []
    snippets = soup.find_all("div", class_=["snippet", "news-snippet", "video-snippet", "card"])

    for item in snippets:
        if len(organic_results) >= limit:
            break

        link_tag = item.find("a", href=True)
        if not link_tag:
            continue

        link = link_tag["href"]
        if not link.startswith(("http://", "https://")):
            continue

        if filter_domain and filter_domain not in link:
            continue

        title_node = item.find("div", class_=["title", "snippet-title"]) or link_tag
        title = _clean_text(title_node.get_text(strip=True)) if title_node else ""

        snippet_node = item.find(
            "div",
            class_=["snippet-content", "description", "snippet-description"],
        )
        snippet = _clean_text(snippet_node.get_text(strip=True)) if snippet_node else _clean_text(
            item.get_text(" ", strip=True)
        )

        date_node = item.find("span", class_=["age", "date", "time", "snippet-age"])
        date_text = _clean_text(date_node.get_text(strip=True)) if date_node else None

        if len(title) < 5 or len(snippet) < 30:
            continue

        result = {
            "position": len(organic_results) + 1,
            "title": title,
            "link": link,
            "snippet": snippet,
            "domain": link.split("/")[2],
        }

        if date_text:
            result["date"] = date_text

        organic_results.append(result)

    payload = {
        "status": "success",
        "searchParameters": {
            "query": query,
            "engine": "brave",
            "type": "search",
            "fetched_at": datetime.now().isoformat(),
            "latency_ms": int((time.time() - start) * 1000),
        },
        "organic_results": organic_results,
        "debug": {
            "user_agent": headers.get("User-Agent"),
            "ip": headers.get("X-Forwarded-For"),
            "result_count": len(organic_results),
        },
    }

    _save_cache(query, payload)
    return payload


class PersonaSearchService:
    def search(self, query: str, limit: int = 12, filter_domain: Optional[str] = None) -> Dict:
        return brave_search(query, limit=limit, filter_domain=filter_domain)
