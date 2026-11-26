#!/usr/bin/env python3
"""把 nodes.txt(订阅 base64) 转成一份给 OpenWrt 路由器用的轻量 clash/mihomo 配置。
目标：内存占用低（无 geosite/geoip/rule-provider），只靠 MATCH 全走代理，
中国 IP 由 ShellCrash 的 cn_ip_route 在防火墙层直连。
"""
import base64
import os
import sys
from urllib.parse import urlsplit, parse_qs, unquote


def b64decode_text(raw: str) -> str:
    raw = raw.strip()
    if "://" in raw:
        return raw
    pad = raw + "=" * (-len(raw) % 4)
    try:
        return base64.b64decode(pad).decode("utf-8", "replace")
    except Exception:
        return raw


def parse_vless(uri: str):
    u = urlsplit(uri.strip())
    if u.scheme != "vless":
        return None
    q = parse_qs(u.query)
    name = unquote(u.fragment) if u.fragment else f"{u.hostname}:{u.port}"
    item = {
        "name": name,
        "type": "vless",
        "server": u.hostname,
        "port": int(u.port or 443),
        "uuid": unquote(u.username or ""),
        "udp": True,
        "tls": True,
        "skip-cert-verify": False,
        "client-fingerprint": q.get("fp", ["chrome"])[0],
        "network": q.get("type", ["ws"])[0],
        "servername": q.get("sni", q.get("peer", [u.hostname]))[0],
    }
    if item["network"] == "ws":
        item["ws-opts"] = {
            "path": q.get("path", ["/"])[0],
            "headers": {"Host": q.get("host", [item["servername"]])[0]},
        }
    return item


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "public/nodes.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "public/router.yaml"
    with open(src, "r", encoding="utf-8") as f:
        text = b64decode_text(f.read())
    proxies = [p for p in (parse_vless(line) for line in text.splitlines()) if p]
    if not proxies:
        print("no nodes parsed, skip", file=sys.stderr)
        return 1

    names = [p["name"] for p in proxies]
    head = f"""# 由 GitHub Actions 自动生成：住宅节点轻量配置（无 geosite，省内存）
mixed-port: 7890
redir-port: 7892
tproxy-port: 7893
allow-lan: true
bind-address: '*'
mode: rule
log-level: warning
ipv6: false
external-controller: :9999
external-ui: ui
unified-delay: true
tcp-concurrent: true
find-process-mode: 'off'
global-client-fingerprint: chrome
profile:
  store-selected: true
  store-fake-ip: true
dns:
  enable: true
  ipv6: false
  listen: 0.0.0.0:1053
  enhanced-mode: redir-host
  proxy-server-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
  fallback:
    - 1.1.1.1
    - 8.8.8.8
proxies:
"""
    lines = [head.rstrip("\n")]
    for p in proxies:
        lines.append(f"  - name: {p['name']}")
        lines.append("    type: vless")
        lines.append(f"    server: {p['server']}")
        lines.append(f"    port: {p['port']}")
        lines.append(f"    uuid: {p['uuid']}")
        lines.append("    udp: true")
        lines.append("    tls: true")
        lines.append("    skip-cert-verify: false")
        lines.append(f"    servername: {p['servername']}")
        lines.append(f"    client-fingerprint: {p['client-fingerprint']}")
        lines.append("    network: ws")
        lines.append("    ws-opts:")
        lines.append(f"      path: {p['ws-opts']['path']}")
        lines.append("      headers:")
        lines.append(f"        Host: {p['ws-opts']['headers']['Host']}")

    lines.append("")
    lines.append("proxy-groups:")
    lines.append("  - name: 🚀 节点选择")
    lines.append("    type: select")
    lines.append("    proxies:")
    lines.append("      - ♻️ 自动选择")
    lines.append("      - 🏠 住宅节点")
    lines.append("      - DIRECT")
    lines.append("  - name: 🏠 住宅节点")
    lines.append("    type: select")
    lines.append("    proxies:")
    for n in names:
        lines.append(f"      - {n}")
    lines.append("  - name: ♻️ 自动选择")
    lines.append("    type: url-test")
    lines.append("    url: 'https://cp.cloudflare.com/generate_204'")
    lines.append("    interval: 900")
    lines.append("    lazy: true")
    lines.append("    proxies:")
    for n in names:
        lines.append(f"      - {n}")
    lines.append("")
    lines.append("rules:")
    lines.append("  - MATCH,♻️ 自动选择")
    lines.append("")

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"router.yaml written: {dst}, proxies={len(proxies)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
