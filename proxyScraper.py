import argparse
import asyncio
import platform
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup


class Scraper:
    def __init__(self, method, url_template):
        self.method = method
        self.url_template = url_template

    def get_url(self, **kwargs):
        return self.url_template.format(method=self.method, **kwargs)

    async def get_response(self, client):
        return await client.get(self.get_url())

    async def handle(self, response):
        return response.text

    async def scrape(self, client):
        response = await self.get_response(client)
        proxies = await self.handle(response)
        pattern = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d{1,5}")
        return re.findall(pattern, proxies)


class SpysMeScraper(Scraper):
    def __init__(self, method):
        super().__init__(method, "https://spys.me/{mode}.txt")

    def get_url(self, **kwargs):
        mode = "proxy" if self.method == "http" else "socks"
        if mode not in ["proxy", "socks"]:
            raise NotImplementedError(f"Method {self.method} not supported by SpysMeScraper")
        return super().get_url(mode=mode, **kwargs)


class ProxyScrapeScraper(Scraper):
    def __init__(self, method, timeout=1000, country="All"):
        super().__init__(method, "https://api.proxyscrape.com/?request=getproxies&proxytype={method}&timeout={timeout}&country={country}")
        self.timeout = timeout
        self.country = country

    def get_url(self, **kwargs):
        return super().get_url(timeout=self.timeout, country=self.country, **kwargs)


class GeoNodeScraper(Scraper):
    def __init__(self, method, limit=500, page=1, sort_by="lastChecked", sort_type="desc"):
        super().__init__(method, "https://proxylist.geonode.com/api/proxy-list?limit={limit}&page={page}&sort_by={sort_by}&sort_type={sort_type}")
        self.limit = limit
        self.page = page
        self.sort_by = sort_by
        self.sort_type = sort_type

    def get_url(self, **kwargs):
        return super().get_url(limit=self.limit, page=self.page, sort_by=self.sort_by, sort_type=self.sort_type, **kwargs)


class ProxyListDownloadScraper(Scraper):
    def __init__(self, method, anon):
        super().__init__(method, "https://www.proxy-list.download/api/v1/get?type={method}&anon={anon}")
        self.anon = anon

    def get_url(self, **kwargs):
        return super().get_url(anon=self.anon, **kwargs)


class GeneralTableScraper(Scraper):
    async def handle(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        proxies = set()
        table = soup.find("table", attrs={"class": "table table-striped table-bordered"})
        if table:
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) > 1:
                    proxy = f"{cells[0].text.strip()}:{cells[1].text.strip()}"
                    proxies.add(proxy)
        return "\n".join(proxies)


scrapers = [
    SpysMeScraper("http"),
    SpysMeScraper("socks"),
    ProxyScrapeScraper("http"),
    ProxyScrapeScraper("socks4"),
    ProxyScrapeScraper("socks5"),
    GeoNodeScraper("socks"),
    ProxyListDownloadScraper("https", "elite"),
    ProxyListDownloadScraper("http", "elite"),
    ProxyListDownloadScraper("http", "transparent"),
    ProxyListDownloadScraper("http", "anonymous"),
    GeneralTableScraper("https"),
    GeneralTableScraper("http"),
]


def verbose_print(verbose, message):
    if verbose:
        print(message)


async def scrape(method, output, verbose):
    start_time = time.time()
    methods = [method]
    if method == "socks":
        methods += ["socks4", "socks5"]

    proxy_scrapers = [s for s in scrapers if s.method in methods]
    if not proxy_scrapers:
        raise ValueError("Method not supported")

    verbose_print(verbose, "Scraping proxies...")
    proxies = []
    tasks = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for scraper in proxy_scrapers:
            tasks.append(scraper.scrape(client))

        results = await asyncio.gather(*tasks)
        for result in results:
            proxies.extend(result)

    verbose_print(verbose, f"Writing {len(proxies)} proxies to file...")
    with open(output, "w") as f:
        f.write("\n".join(proxies))
    verbose_print(verbose, "Done!")
    verbose_print(verbose, f"Took {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--proxy",
        help="Supported proxy type: " + ", ".join(sorted(set(s.method for s in scrapers))),
        required=True,
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file name to save .txt file",
        default="output.txt",
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Increase output verbosity",
        action="store_true",
    )
    args = parser.parse_args()

    if sys.version_info >= (3, 7) and platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(scrape(args.proxy, args.output, args.verbose))
