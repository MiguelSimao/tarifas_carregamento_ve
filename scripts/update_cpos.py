import os
import urllib.request

URL = "https://raw.githubusercontent.com/AmmeProjects/open-data/refs/heads/main/data/naps/portugal/cpos.json"
OUTPUT_PATH = os.path.join("data", "cpos.json")


def fetch_cpos():
    print(f"Fetching newest version of cpos.json from {URL}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "tarifas-carregamento-ve/1.0"},
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()

    with open(OUTPUT_PATH, "wb") as f:
        f.write(content)

    print(f"Successfully saved {len(content)} bytes to {OUTPUT_PATH}")


if __name__ == "__main__":
    fetch_cpos()
