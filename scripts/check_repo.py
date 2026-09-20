#!/usr/bin/env python3
"""Offline repository, public-content and regression checks (stdlib only)."""

from pathlib import Path
import json
import re
import subprocess
import sys
from urllib.parse import unquote

from validate_contract import validate, validate_prompt
from evidence_contract import compile_contract

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = []
    required = ["SKILL.md", "README.md", "LICENSE", "agents/openai.yaml", "docs/validation.md", "examples/contract.json", "examples/evidence-contract.input.json"]
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f"Missing {name}")
    if errors:
        print("\n".join(errors))
        return 1
    skill = (ROOT / "SKILL.md").read_text()
    if not skill.startswith("---\n") or len(skill.splitlines()) > 500:
        errors.append("Invalid SKILL frontmatter or excessive length")
    frontmatter = skill.split("---", 2)[1]
    if set(re.findall(r"^(\w+):", frontmatter, re.M)) != {"name", "description"}:
        errors.append("SKILL requires name and description frontmatter only")
    for ref in (ROOT / "references").glob("*.md"):
        if f"`references/{ref.name}`" not in skill:
            errors.append(f"Unrouted reference: {ref.name}")
    patterns = {
        "personal absolute path": r"/(?:Users|home)/[A-Za-z0-9_.-]+/",
        "GitHub token": r"gh[pousr]_[A-Za-z0-9]{20,}",
        "private key": r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
        "referral code": r"[?&]inviteCode=",
        "private source link": r"https?://[^\s/]+\.feishu\.cn/(?:wiki|docx)/",
    }
    public_docs = list(ROOT.rglob("*.md")) + list((ROOT / "agents").glob("*.yaml")) + list((ROOT / "examples").glob("*.json"))
    for path in public_docs:
        if ".git" in path.parts:
            continue
        text = path.read_text()
        rel = path.relative_to(ROOT)
        if path.suffix == ".md" and text.count("```") % 2:
            errors.append(f"Unbalanced code fence: {rel}")
        for description, pattern in patterns.items():
            if re.search(pattern, text):
                errors.append(f"Possible {description}: {rel}")
        if path.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in link or link.startswith("#"):
                    continue
                target = unquote(link.split("#", 1)[0])
                if target and not (path.parent / target).is_file():
                    errors.append(f"Broken local link in {rel}: {target}")
    fixture = json.loads((ROOT / "examples/contract.json").read_text())
    errors.extend(validate(fixture, ROOT / "examples"))
    evidence_fixture = json.loads((ROOT / "examples/evidence-contract.input.json").read_text())
    try:
        compiled = compile_contract(evidence_fixture)
        errors.extend(validate(compiled, ROOT / "examples"))
        if not validate(compiled, ROOT / "examples", require_reviewed=True):
            errors.append("Unreviewed teaching fixture unexpectedly passed the strict gate")
    except ValueError as exc:
        errors.append(str(exc))
    product = (ROOT / "examples/02-product-unfolding.md").read_text()
    prompt = product.split("## H3 FL2VA 可复制块", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    errors.extend(validate_prompt(prompt, "FL2VA", 8, True))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_*.py"], cwd=ROOT)
    if result.returncode:
        return result.returncode
    print("Repository, local links, public-text heuristics, example contracts and regression checks passed.")
    print("This does not verify source-video interpretation, provider execution or generated-video similarity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
