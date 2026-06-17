# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""asta-news 分级配置读取器：`config/tiers.yaml` 是各级（group/daily/full）数量与阈值的**唯一事实源**。

凡是需要"日报选几条 / 精选选几条 / 用什么分数阈值与多样性约束"的地方——SKILL.md、
curation.md、editor 裁决、生成的 build_digest.py——都从这里读，别再把 5 / 8 / 20 这类数字写死在别处。
本地可用 `$DATA/tiers.local.yaml` 同键深合并覆盖（不进 git，给单机调参用）。

用法:
  tiers.py                      # 打印完整 tiers 配置（JSON），喂给 build 脚本/agent
  tiers.py --summary            # 人读摘要：各级 target/max/阈值/多样性约束
  tiers.py --get daily.target   # 取单个值（点路径），如 daily.target -> 20、group.max -> 8
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CONFIG = PLUGIN_ROOT / "config" / "tiers.yaml"


def data_dir() -> Path:
    for env in ("ASTA_NEWS_HOME", "CLAUDE_PLUGIN_DATA"):
        if os.environ.get(env):
            return Path(os.environ[env]).expanduser()
    return Path.home() / ".claude" / "plugins" / "data" / "asta-news"


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_tiers() -> dict:
    """返回 {full, daily, group} 三级配置。config/tiers.yaml + 可选 $DATA/tiers.local.yaml 深合并。"""
    doc = yaml.safe_load(CONFIG.read_text()) or {}
    tiers = doc.get("tiers", doc)  # 容忍裸 dict 或包了一层 tiers:
    local = data_dir() / "tiers.local.yaml"
    if local.exists():
        loc = yaml.safe_load(local.read_text()) or {}
        _deep_merge(tiers, loc.get("tiers", loc))
    return tiers


def _get(tiers: dict, path: str):
    cur = tiers
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"tiers 配置里没有 '{path}'（在 '{part}' 处断）")
        cur = cur[part]
    return cur


def _summary(tiers: dict) -> str:
    L = ["分级配置（唯一源 config/tiers.yaml）："]
    for key in ("group", "daily", "full"):
        t = tiers.get(key, {})
        if key == "full":
            L.append(f"  full  {t.get('label','')}：不限量（仅去重，全部候选）")
            continue
        L.append(
            f"  {key:5s} {t.get('label','')}：目标 {t.get('target','—')} / 上限 {t.get('max','—')}"
            f" · 分阈 {t.get('score_threshold','—')} · ≥{t.get('min_layers','—')} 层"
            f" · 单层≤{t.get('max_per_layer','—')} · 单源≤{t.get('max_per_source','—')}"
        )
    L.append("  注：daily 用 daily 阈值（更低），不要拿 group 的严格度卡 daily——那正是此前日报掉到个位数的原因。")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true", help="人读摘要")
    ap.add_argument("--get", metavar="PATH", help="取单个值，点路径如 daily.target")
    args = ap.parse_args()

    tiers = load_tiers()
    if args.get:
        try:
            v = _get(tiers, args.get)
        except KeyError as e:
            print(e, file=sys.stderr)
            return 2
        print(v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False))
        return 0
    if args.summary:
        print(_summary(tiers))
        return 0
    print(json.dumps(tiers, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
