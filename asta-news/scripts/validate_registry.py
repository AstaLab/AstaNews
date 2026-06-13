# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""校验 AstaNews 配置完整性：源注册表 schema + 模块化配置 + manifest。

贡献 PR 的质量门：id 唯一、layer/type/parser/priority 合法、必填字段齐全、
json/yaml 可解析。CI 与本地共用。退出码 0=通过 / 1=有错。

用法:  uv run asta-news/scripts/validate_registry.py
"""
import glob
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LAYERS = {"model", "post-training", "eval", "data", "infra", "serving", "maas",
          "agent", "embodied", "safety", "product", "business", "devtool"}
TYPES = {"rss", "atom", "json", "github-releases", "rsshub", "html"}
PARSERS = {"hn_algolia", "hf_daily_papers", "openrouter_models", "oss_insight",
           "github_org_repos", "github_releases_api", "swebench", "mcp_registry",
           "hf_hub_list", "reddit_top", "kaggle_datasets", "evalplus", "aider_yaml", "generic"}
PRIOS = {"P0", "P1", "P2"}


def main() -> int:
    errs: list[str] = []
    ids: set[str] = set()
    n = 0
    for f in sorted(glob.glob(str(ROOT / "sources" / "*.yaml"))):
        name = Path(f).name
        try:
            doc = yaml.safe_load(open(f)) or {}
        except Exception as e:
            errs.append(f"{name}: YAML 解析失败 {e}")
            continue
        for s in doc.get("sources", []):
            n += 1
            sid = s.get("id", "?")
            where = f"{name}:{sid}"
            for k in ("id", "name", "layers", "type", "url", "priority", "freq", "verified"):
                if k not in s:
                    errs.append(f"{where}: 缺字段 {k}")
            if sid in ids:
                errs.append(f"{where}: id 重复")
            ids.add(sid)
            if not isinstance(s.get("layers"), list) or not set(s.get("layers", [])) <= LAYERS:
                errs.append(f"{where}: layers 非法 {s.get('layers')}")
            if s.get("type") not in TYPES:
                errs.append(f"{where}: type 非法 {s.get('type')}")
            if s.get("type") == "json" and s.get("parser") not in PARSERS:
                errs.append(f"{where}: json 源 parser 非法/缺失 {s.get('parser')}")
            if s.get("priority") not in PRIOS:
                errs.append(f"{where}: priority 非法 {s.get('priority')}")

    # 模块化配置可解析
    for f in glob.glob(str(ROOT / "config" / "*.yaml")):
        try:
            yaml.safe_load(open(f))
        except Exception as e:
            errs.append(f"config/{Path(f).name}: {e}")
    for f in (ROOT / "rules.yaml",):
        try:
            yaml.safe_load(open(f))
        except Exception as e:
            errs.append(f"rules.yaml: {e}")

    # manifest
    for f in (ROOT / ".claude-plugin" / "plugin.json", ROOT.parent / ".claude-plugin" / "marketplace.json"):
        try:
            json.load(open(f))
        except Exception as e:
            errs.append(f"{f.name}: {e}")

    if errs:
        print(f"✗ {len(errs)} 处问题：", file=sys.stderr)
        print("\n".join("  - " + e for e in errs), file=sys.stderr)
        return 1
    print(f"✓ 校验通过：{n} 源（{len(ids)} 唯一 id）+ 配置 + manifest 全部合法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
