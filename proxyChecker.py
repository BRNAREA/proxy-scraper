import argparse
import random
import re
import socket
import threading
import urllib.request
from time import time
from pathlib import Path
import socks

# Obter o diretório atual do script
current_dir = Path(__file__).resolve().parent
user_agents_file = current_dir / 'user_agents.txt'

# Carregar os user agents do arquivo
user_agents = []
with open(user_agents_file, "r") as f:
    user_agents = [line.strip() for line in f]

class Proxy:
    def __init__(self, method, proxy):
        if method.lower() not in ["http", "https", "socks4", "socks5"]:
            raise NotImplementedError("Only HTTP, HTTPS, SOCKS4, and SOCKS5 are supported")
        self.method = method.lower()
        self.proxy = proxy

    def is_valid(self):
        return re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{1,5}$", self.proxy) is not None

    def check(self, site, timeout, user_agent, verbose):
        proxy_host, proxy_port = self.proxy.split(':')
        if self.method in ["socks4", "socks5"]:
            socks.set_default_proxy(socks.SOCKS4 if self.method == "socks4" else socks.SOCKS5, proxy_host, int(proxy_port))
            socket.socket = socks.socksocket

        try:
            start_time = time()
            if self.method in ["http", "https"]:
                proxy_url = f"{self.method}://{self.proxy}"
                proxy_handler = urllib.request.ProxyHandler({self.method: proxy_url})
                opener = urllib.request.build_opener(proxy_handler)
                urllib.request.install_opener(opener)
                req = urllib.request.Request(site, headers={"User-Agent": user_agent})
                urllib.request.urlopen(req, timeout=timeout)
            else:
                urllib.request.urlopen(site, timeout=timeout)
            end_time = time()
            time_taken = end_time - start_time
            verbose_print(verbose, f"Proxy {self.proxy} is valid, time taken: {time_taken}")
            return True, time_taken, None
        except Exception as e:
            verbose_print(verbose, f"Proxy {self.proxy} is not valid, error: {str(e)}")
            return False, 0, e

    def __str__(self):
        return self.proxy

def verbose_print(verbose, message):
    if verbose:
        print(message)

def check_proxies(file, timeout, method, site, verbose, random_user_agent):
    proxies = []
    with open(file, "r") as f:
        proxies = [Proxy(method, line.strip()) for line in f]

    print(f"Checking {len(proxies)} proxies")
    proxies = list(filter(lambda x: x.is_valid(), proxies))
    valid_proxies = []
    
    def check_proxy(proxy, user_agent):
        if random_user_agent:
            user_agent = random.choice(user_agents)
        valid, time_taken, error = proxy.check(site, timeout, user_agent, verbose)
        if valid:
            valid_proxies.append(proxy)

    threads = []
    for proxy in proxies:
        user_agent = random.choice(user_agents) if random_user_agent else random.choice(user_agents)
        t = threading.Thread(target=check_proxy, args=(proxy, user_agent))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    with open(file, "w") as f:
        for proxy in valid_proxies:
            f.write(str(proxy) + "\n")

    print(f"Found {len(valid_proxies)} valid proxies")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--timeout", type=int, help="Dismiss the proxy after -t seconds", default=20)
    parser.add_argument("-p", "--proxy", help="Check HTTPS, HTTP, SOCKS4, or SOCKS5 proxies", default="http")
    parser.add_argument("-l", "--list", help="Path to your proxy list file", default="output.txt")
    parser.add_argument("-s", "--site", help="Check with specific website like google.com", default="https://google.com/")
    parser.add_argument("-v", "--verbose", help="Increase output verbosity", action="store_true")
    parser.add_argument("-r", "--random_agent", help="Use a random user agent per proxy", action="store_true")
    args = parser.parse_args()

    check_proxies(file=args.list, timeout=args.timeout, method=args.proxy, site=args.site, verbose=args.verbose, random_user_agent=args.random_agent)
