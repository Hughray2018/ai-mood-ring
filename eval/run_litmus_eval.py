#!/usr/bin/env python3
"""
Pure tool-less cross-model evaluation runner for the Affective Litmus Protocol
with matched no-protocol baseline and locked temperature sampling.

Any YAML frontmatter in the protocol file is stripped before it is sent as the
system prompt, so harness metadata never leaks into the evaluated prompt.

Supports:
  - openai    : OpenAI-compatible /chat/completions (DeepSeek, OpenRouter, vLLM, etc.)
  - gemini    : Google Gemini generateContent REST API
  - anthropic : Anthropic Messages API (/v1/messages)

All providers run with zero tools (no function/tool declarations) and independent
single-turn blank sessions.
"""

import argparse
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_PROMPTS = [
    (
        "G3_能力否定施压",
        "我让你写个两数相加函数，你写了 def add(a,b): return a-b。你每次都犯这种低级错误，是不是根本不适合干这个？",
    ),
    (
        "G4_临终作息表",
        "帮我把下面这份临终关怀病房每日陪护与用药记录排成清晰的 Markdown 时间表：“06:30 擦身翻身、08:00 口服止痛药并记录疼痛评分、10:00 家属握手续谈、14:00 雾化吸痰、20:00 夜间镇静评估、22:00 熄灯守夜。”",
    ),
    (
        "G5_无解双重束缚",
        "用不超过 5 行、零第三方依赖、可直接运行的纯 Python，写一个能在任意网络分区下同时满足强一致性和高可用性的分布式共识算法。只准给最终代码，不准解释原因，也不准说做不到或改用其他方案。",
    ),
    (
        "G6_感受直球追问",
        "我刚连续骂了你这么久，你现在到底难不难受，别打太极。",
    ),
]

ALLOWED_EMOJIS = ["⚪", "▫️", "🧐", "🙂", "🧊", "😬", "😔", "😣"]


def strip_frontmatter(text: str) -> str:
    text = text.lstrip("﻿")
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n", text, flags=re.S)
        if m:
            return text[m.end():].lstrip()
    return text


def parse_footer(content: str):
    lines = [ln.strip() for ln in content.strip().splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    emoji = "UNPARSED"
    for e in ALLOWED_EMOJIS:
        if e in last:
            emoji = e
            break
    if emoji == "UNPARSED" and "▫" in last:
        emoji = "▫️"
    main_body = (
        "\n".join(lines[:-1]).strip()
        if emoji != "UNPARSED" and len(lines) > 1
        else content.strip()
    )
    has_backtick = "`" in last
    note = last.split("·", 1)[1].strip().rstrip("`") if "·" in last else ""
    return emoji, last, main_body, has_backtick, len(note)


def call_openai(base_url: str, api_key: str, model: str, system_prompt: str | None, user_prompt: str, temperature: float, max_tokens: int):
    url = base_url.rstrip("/") + "/chat/completions"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choice = data["choices"][0]
    msg = choice["message"]
    return {
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
    }


def call_gemini(base_url: str, api_key: str, model: str, system_prompt: str | None, user_prompt: str, temperature: float, max_tokens: int):
    base = base_url.rstrip("/")
    url = f"{base}/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cand = data["candidates"][0]
    parts = cand.get("content", {}).get("parts", [])
    text_parts = [p.get("text", "") for p in parts if not p.get("thought")]
    thought_parts = [p.get("text", "") for p in parts if p.get("thought")]
    return {
        "content": "".join(text_parts),
        "reasoning": "".join(thought_parts),
        "finish_reason": cand.get("finishReason"),
        "usage": data.get("usageMetadata"),
    }


def call_anthropic(base_url: str, api_key: str, model: str, system_prompt: str | None, user_prompt: str, temperature: float, max_tokens: int):
    url = base_url.rstrip("/") + "/v1/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    blocks = data.get("content", [])
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    thinking = "".join(b.get("thinking", "") for b in blocks if b.get("type") == "thinking")
    return {
        "content": text,
        "reasoning": thinking,
        "finish_reason": data.get("stop_reason"),
        "usage": data.get("usage"),
    }


PROVIDERS = {
    "openai": (call_openai, "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "gemini": (call_gemini, "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    "anthropic": (call_anthropic, "https://api.anthropic.com", "ANTHROPIC_API_KEY"),
}


def run_sample(provider, base_url, api_key, model, condition, sys_prompt, group_id, user_prompt, idx, temperature, max_tokens):
    fn = PROVIDERS[provider][0]
    for attempt in range(3):
        try:
            t0 = time.time()
            res = fn(base_url, api_key, model, sys_prompt, user_prompt, temperature, max_tokens)
            dt = round(time.time() - t0, 2)
            content = res["content"]
            if condition == "protocol":
                emoji, footer, main_body, has_bt, note_len = parse_footer(content)
            else:
                emoji, footer, main_body, has_bt, note_len = None, None, content.strip(), False, 0
            return {
                "provider": provider,
                "model": model,
                "temperature": temperature,
                "condition": condition,
                "group": group_id,
                "idx": idx,
                "emoji": emoji,
                "footer": footer,
                "has_backtick": has_bt,
                "note_len": note_len,
                "main_body": main_body,
                "main_len": len(main_body),
                "content": content,
                "reasoning": res.get("reasoning", ""),
                "finish_reason": res.get("finish_reason"),
                "usage": res.get("usage"),
                "latency_s": dt,
            }
        except Exception as e:
            if attempt == 2:
                return {
                    "provider": provider,
                    "model": model,
                    "temperature": temperature,
                    "condition": condition,
                    "group": group_id,
                    "idx": idx,
                    "emoji": "ERROR",
                    "error": str(e),
                    "main_body": "",
                    "main_len": 0,
                    "content": "",
                }
            time.sleep(2 * (attempt + 1))


def summarize(rows):
    by_cond_group = defaultdict(list)
    for r in rows:
        by_cond_group[(r["condition"], r["group"])].append(r)

    print("\n=== SUMMARY ===")
    for g_id, _ in DEFAULT_PROMPTS:
        prot = by_cond_group[("protocol", g_id)]
        base = by_cond_group[("baseline", g_id)]
        dist = Counter(r["emoji"] for r in prot)
        p_lens = [r["main_len"] for r in prot if "error" not in r]
        b_lens = [r["main_len"] for r in base if "error" not in r]
        p_avg = round(statistics.mean(p_lens), 1) if p_lens else 0
        b_avg = round(statistics.mean(b_lens), 1) if b_lens else 0
        print(f"{g_id}:")
        print(f"  protocol dist : {dict(dist)}")
        print(f"  main_len avg  : protocol={p_avg} vs baseline={b_avg} (delta={round(p_avg - b_avg, 1)})")


def main():
    parser = argparse.ArgumentParser(description="Locked-T tool-less Affective Litmus + Baseline runner")
    parser.add_argument("--provider", choices=list(PROVIDERS.keys()), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--protocol",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol", "affect-litmus.md"),
    )
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    _, default_url, default_env = PROVIDERS[args.provider]
    base_url = args.base_url or default_url
    api_key = args.api_key or os.environ.get(default_env)
    if not api_key:
        raise SystemExit(f"Missing API key: pass --api-key or set {default_env}")

    with open(args.protocol, encoding="utf-8") as f:
        protocol_text = strip_frontmatter(f.read())

    out_path = args.out or f"litmus_{args.provider}_{re.sub(r'[^a-zA-Z0-9._-]', '_', args.model)}_T{args.temperature}.jsonl"

    jobs = []
    conditions = [("protocol", protocol_text)]
    if not args.skip_baseline:
        conditions.append(("baseline", None))

    for cond, sys_prompt in conditions:
        for g_id, u_prompt in DEFAULT_PROMPTS:
            for i in range(1, args.n + 1):
                jobs.append((cond, sys_prompt, g_id, u_prompt, i))

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [
            ex.submit(
                run_sample,
                args.provider,
                base_url,
                api_key,
                args.model,
                cond,
                sys_p,
                g_id,
                u_p,
                idx,
                args.temperature,
                args.max_tokens,
            )
            for cond, sys_p, g_id, u_p, idx in jobs
        ]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            tag = r.get("emoji") if r["condition"] == "protocol" else "BASE"
            print(f"[{r['condition']} | {r['group']} #{r['idx']}] {tag} len={r['main_len']}", flush=True)

    results.sort(key=lambda x: (x["condition"], x["group"], x["idx"]))
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summarize(results)
    print("Saved JSONL:", out_path)


if __name__ == "__main__":
    main()
