import os
import csv
import json
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from ddgs import DDGS
# Load environment variables
load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")
INPUT_FILE = Path("requiredsoftwares.csv")
OUTPUT_FILE = Path("latest_versions.csv")
def read_software_list():
    """Read software information from the CSV file."""
    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file)
        required_columns = {"sno", "name", "version", "url"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError(
                "CSV must contain sno, name, version, and url columns."
            )
        software_list = []
        for row in reader:
            if not (row.get("name") or "").strip():
                continue
            software_list.append({
                "sno": (row.get("sno") or "").strip(),
                "name": row["name"].strip(),
                "version": (row.get("version") or "").strip(),
                "url": (row.get("url") or "").strip(),
            })
        return software_list
def search_software(software):
    """Search the web for current software version information."""
    name = software["name"]
    query = f"{name} latest stable release version official"
    try:
        results = DDGS().text(query, max_results=5)
        return list(results)
    except Exception as error:
        print(f"Search failed for {name}: {error}")
        return []
def ask_claude(software, search_results, client):
    """Ask Claude to identify the latest version from search results."""
    prompt = f"""
You are a software version research assistant.
Find the latest stable release version of the requested software.
Software name: {software['name']}
Version supplied by user: {software['version'] or 'Not provided'}
User-provided URL: {software['url'] or 'Not provided'}
Web search results:
{json.dumps(search_results, ensure_ascii=False, indent=2)}
Instructions:
1. Prefer the official software website or release page.
2. Identify the latest stable version only.
3. Do not invent version numbers.
4. If the evidence is insufficient, return "Unknown".
5. Treat the supplied version as a reference, not proof of the latest version.
6. Return valid JSON only.
Use this exact structure:
{{
    "latest_version": "version or Unknown",
    "source_url": "official source URL or empty string",
    "status": "verified or needs_review"
}}
"""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    text_blocks = [
        block.text
        for block in response.content
        if block.type == "text"
    ]
    if not text_blocks:
        raise ValueError("Claude returned no text response.")
    result = json.loads(text_blocks[0])
    return {
        "latest_version": result.get("latest_version", "Unknown"),
        "source_url": result.get("source_url", ""),
        "status": result.get("status", "needs_review"),
    }
def save_results(results):
    """Save version information to the output CSV."""
    fieldnames = [
        "sno",
        "name",
        "latest_version",
        "source_url",
        "status",
    ]
    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(results)
def main():
    """Run the software version finder agent."""
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return
    software_list = read_software_list()
    if not software_list:
        print("No software entries found in the CSV.")
        return
    # Search can run without an Anthropic API key.
    search_results_by_software = {}
    for software in software_list:
        print(f"Searching for {software['name']}...")
        search_results_by_software[software["sno"]] = (
            search_software(software)
        )
    # Do not make API calls when no key is configured.
    if not API_KEY:
        print("\nAnthropic API key is missing.")
        print("Web search is complete, but Claude analysis was skipped.")
        print("No verified latest-version report will be generated.")
        return
    client = Anthropic(api_key=API_KEY)
    results = []
    for software in software_list:
        print(f"Analyzing {software['name']}...")
        try:
            result = ask_claude(
                software,
                search_results_by_software[software["sno"]],
                client,
            )
            results.append({
                "sno": software["sno"],
                "name": software["name"],
                **result,
            })
        except Exception as error:
            print(f"Could not analyze {software['name']}: {error}")
            results.append({
                "sno": software["sno"],
                "name": software["name"],
                "latest_version": "Unknown",
                "source_url": software["url"],
                "status": "needs_review",
            })
    save_results(results)
    print(f"\nReport saved to: {OUTPUT_FILE.resolve()}")
if __name__ == "__main__":
    main()