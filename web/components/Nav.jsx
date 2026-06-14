"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { API } from "../lib/config";

const ITEMS = [
  { label: "今日日报", path: "/" },
  { label: "往期", path: "/archive" },
  { label: "搜索", path: "/search" },
  { label: "控制台", path: "/console", admin: true }, // 仅本地连后端时显示，不进公开站
  { label: "关于", path: "/about" },
];

export default function Nav() {
  const p = usePathname() || "/";
  const norm = (x) => (x.length > 1 ? x.replace(/\/$/, "") : x);
  const cur = norm(p);
  return (
    <nav className="topnav">
      {ITEMS.filter((it) => !it.admin || API).map((it) => {
        const active = it.path === "/" ? cur === "/" : cur.startsWith(it.path);
        return (
          <Link key={it.path} href={it.path} className={active ? "active" : ""}>{it.label}</Link>
        );
      })}
    </nav>
  );
}
