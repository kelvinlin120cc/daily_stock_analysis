# -*- coding: utf-8 -*-
"""
===================================
公开报告接口（无需认证）
===================================

职责：
1. 提供 GET /public/report/<record_id> 分享报告页面
2. 通过嵌入 token 实现免登录查看单份报告
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from api.deps import get_database_manager
from src.storage import DatabaseManager
from src.services.history_service import HistoryService

logger = logging.getLogger(__name__)

router = APIRouter()

_SHARE_SECRET_FILE = ".share_secret"

# JavaScript module (kept separate from f-string to avoid brace-escaping issues)
_SHARE_PAGE_JS = """
<script src="https://unpkg.com/marked/marked.min.js"></script>
<script>
(function(){
  try {
    var _b64 = "__ENCODED_MARKDOWN__";
    var _bytes = Uint8Array.from(atob(_b64), function(c){ return c.charCodeAt(0); });
    window.markdownContent = new TextDecoder('utf-8').decode(_bytes);
    if (typeof marked !== 'undefined') {
      // Configure marked to match react-markdown + remarkGfm behavior
      // GFM: tables, strikethrough, task lists; breaks: single newline → <br>
      marked.setOptions({
        gfm: true,
        breaks: true
      });
      document.getElementById("markdown-content").innerHTML = marked.parse(window.markdownContent);
    } else {
      document.getElementById("markdown-content").textContent = window.markdownContent;
    }
  } catch(e) {
    document.getElementById("markdown-content").textContent = "报告内容加载失败";
  }
})();
function copyMarkdown(){
  if(typeof window.markdownContent === 'undefined') return;
  var text = window.markdownContent;
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(function(){ showToast(); });
  } else {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position="fixed"; ta.style.left="-9999px";
    document.body.appendChild(ta); ta.select(); document.execCommand("copy");
    document.body.removeChild(ta); showToast();
  }
}
function copyPlainText(){
  if(typeof window.markdownContent === 'undefined') return;
  var md = window.markdownContent;
  // Convert markdown to plain text: strip markdown syntax
  var plain = md
    .replace(/^#{1,6}\\s+/gm, '')
    .replace(/^[-*]\\s+/gm, '')
    .replace(/^>\\s?/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/~~(.+?)~~/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^---+$/gm, '')
    .replace(/\\[x[ ]\\]/g, '')
    .trim();
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(plain).then(function(){ showToast(); });
  } else {
    var ta = document.createElement("textarea");
    ta.value = plain; ta.style.position="fixed"; ta.style.left="-9999px";
    document.body.appendChild(ta); ta.select(); document.execCommand("copy");
    document.body.removeChild(ta); showToast();
  }
}
function showToast(){
  var t = document.getElementById("toast");
  if(!t) return;
  t.classList.add("show");
  setTimeout(function(){ t.classList.remove("show"); }, 2000);
}
</script>
</body></html>"""


def _get_data_dir():
    import os
    from pathlib import Path
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return str(Path(db_path).resolve().parent)


def _load_share_secret():
    import os
    import secrets
    from pathlib import Path
    data_dir = Path(_get_data_dir())
    secret_path = data_dir / _SHARE_SECRET_FILE
    try:
        if secret_path.exists():
            secret = secret_path.read_bytes()
            if len(secret) == 32:
                return secret
    except OSError:
        pass
    data_dir.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_bytes(32)
    try:
        tmp_path = secret_path.with_suffix(".tmp")
        tmp_path.write_bytes(new_secret)
        tmp_path.chmod(0o600)
        tmp_path.replace(secret_path)
    except OSError:
        pass
    return new_secret


def _create_share_token(record_id: int) -> str:
    secret = _load_share_secret()
    ts = int(time.time())
    payload = f"{record_id}.{ts}"
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    token = base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode().rstrip("=")
    return token


def _verify_share_token(record_id: int, token: str, max_age_hours: int = 720) -> bool:
    try:
        padded = token + "=" * (4 - len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        parts = decoded.split(".")
        if len(parts) != 3:
            return False
        tok_record_id, ts_str, sig = int(parts[0]), parts[1], parts[2]
        if tok_record_id != record_id:
            return False
        secret = _load_share_secret()
        payload = f"{record_id}.{ts_str}"
        expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        if sig != expected:
            return False
        ts = int(ts_str)
        if time.time() - ts > max_age_hours * 3600:
            return False
        return True
    except (ValueError, TypeError, Exception):
        return False


def _error_html(title: str, icon: str, message: str, color: str) -> HTMLResponse:
    return HTMLResponse(status_code=403 if color == "warning" else 404, content=f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{min-height:100vh;display:flex;align-items:center;justify-content:center;background:hsl(228 35% 7%);color:hsl(210 33% 98%);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans SC",sans-serif}}
  .card{{max-width:480px;padding:2.5rem;border-radius:16px;background:hsl(230 24% 10%);border:1px solid hsl(226 19% 20%);text-align:center;box-shadow:0 18px 48px hsl(215 25% 10% / 0.4)}}
  .icon{{width:56px;height:56px;border-radius:14px;margin:0 auto 1.25rem;display:flex;align-items:center;justify-content:center;font-size:1.5rem}}
  h1{{font-size:1.15rem;color:hsl(var(--fg));margin-bottom:.75rem;font-weight:600}}
  p{{font-size:.9rem;color:hsl(228 16% 72%);line-height:1.7}}
</style></head><body>
<div class="card">
  <div class="icon" style="background:{color}/0.1">{icon}</div>
  <h1>{title}</h1>
  <p>{message}</p>
</div></body></html>""")


class ShareDataResponse(BaseModel):
    stock_name: str
    stock_code: str
    report_language: str
    markdown_content: str


@router.get(
    "/report/{record_id}/data",
    response_model=ShareDataResponse,
    include_in_schema=False,
    summary="获取分享报告数据(JSON)",
)
def share_report_data(
    record_id: int,
    token: Optional[str] = Query(None, description="Share token"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ShareDataResponse:
    """Return report data as JSON for the SPA share page."""
    if not token or not _verify_share_token(record_id, token):
        raise HTTPException(status_code=403, detail="分享链接无效或已过期")

    service = HistoryService(db_manager)
    try:
        markdown_content = service.get_markdown_report(str(record_id))
    except Exception as e:
        logger.error("Share data failed for %s: %s", record_id, e, exc_info=True)
        raise HTTPException(status_code=404, detail="报告不存在")

    if not markdown_content:
        raise HTTPException(status_code=404, detail="报告不存在")

    record = service._resolve_record(str(record_id))
    # Extract report_language from raw_result JSON (stored during analysis)
    report_lang = "zh"
    if record and record.raw_result:
        try:
            import json
            raw = json.loads(record.raw_result)
            report_lang = raw.get("report_language", "zh") or "zh"
        except (json.JSONDecodeError, AttributeError):
            pass
    return ShareDataResponse(
        stock_name=record.name if record else "",
        stock_code=record.code if record else "",
        report_language=report_lang,
        markdown_content=markdown_content,
    )


@router.get(
    "/report/{record_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="查看分享报告(静态页面)",
)
def share_report(
    record_id: int,
    token: Optional[str] = Query(None, description="Share token"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> HTMLResponse:
    if not token or not _verify_share_token(record_id, token):
        return _error_html("分享链接无效", "⚠️", "该分享链接已过期或已被篡改。<br>请联系分享者获取新的链接。", "hsl(37 92% 50%)")

    service = HistoryService(db_manager)
    try:
        markdown_content = service.get_markdown_report(str(record_id))
    except Exception as e:
        logger.error("Share report failed for %s: %s", record_id, e, exc_info=True)
        markdown_content = None

    if not markdown_content:
        return _error_html("报告不存在", "❌", "未找到该分析报告，可能已被删除。", "hsl(349 100% 63%)")

    record = service._resolve_record(str(record_id))
    stock_name = record.name if record else ""
    stock_code = record.code if record else ""
    created_at = str(record.created_at) if record and record.created_at else ""
    display_title = stock_name or stock_code
    display_code_date = f"{stock_code} · {created_at[:16] if created_at else ''} · 分析报告"

    encoded_markdown = base64.b64encode(markdown_content.encode('utf-8')).decode('ascii')

    # CSS styles matching the full report page design (ReportMarkdown component)
    # Supports both light and dark themes via @media (prefers-color-scheme)
    css_styles = """
<style>
  /* ===== Theme Variables (matching dsa-web index.css) ===== */
  :root {
    --bg: hsl(216 33% 97%);
    --bg-card: hsl(0 0% 100%);
    --fg: hsl(228 35% 12%);
    --fg-secondary: hsl(224 18% 28%);
    --fg-muted: hsl(224 12% 35%);
    --border: hsl(218 24% 84% / 0.9);
    --border-strong: hsl(228 35% 12% / 0.16);
    --bg-elevated: hsl(0 0% 100%);
    --bg-subtle: hsl(228 35% 12% / 0.03);
    --cyan: hsl(193 100% 43%);
    --purple: hsl(247 84% 66%);
    --success: hsl(152 69% 40%);
    --cyan-dim: hsl(193 100% 43% / 0.1);
    --purple-dim: hsl(247 84% 66% / 0.08);
    --surface-btn-bg: hsl(214 36% 97% / 0.98);
    --surface-btn-border: hsl(218 24% 84% / 0.94);
    --surface-btn-hover: hsl(214 40% 95% / 0.99);
    --surface-btn-border-hover: hsl(193 100% 43% / 0.22);
    --shadow-card: 0 12px 24px hsl(220 22% 34% / 0.08), 0 4px 10px hsl(220 18% 28% / 0.04);
    --prose-border: hsl(228 35% 12% / 0.1);
    --prose-border-strong: hsl(228 35% 12% / 0.16);
    --prose-blockquote-border: hsl(247 84% 66% / 0.28);
    --prose-blockquote-bg: hsl(247 84% 66% / 0.08);
    --bg-code: hsl(193 100% 43% / 0.1);
    --bg-pre: hsl(0 0% 100% / 0.92);
    --bg-th: hsl(0 0% 100% / 0.92);
    --toast-bg: hsl(152 69% 40%);
    --toast-fg: hsl(210 33% 98%);
    --icon-bg: hsl(247 84% 66% / 0.1);
    --icon-fg: hsl(247 84% 66%);
    --header-border: hsl(218 24% 84% / 0.9);
    --toast-bg-fail: hsl(0 90% 55%);
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --bg: hsl(228 35% 7%);
      --bg-card: hsl(230 24% 10%);
      --fg: hsl(210 33% 98%);
      --fg-secondary: hsl(228 16% 72%);
      --fg-muted: hsl(228 10% 48%);
      --border: hsl(226 19% 20%);
      --border-strong: hsl(210 33% 98% / 0.18);
      --bg-elevated: hsl(230 22% 12%);
      --bg-subtle: hsl(210 33% 98% / 0.05);
      --cyan: hsl(190 100% 50%);
      --purple: hsl(247 84% 72%);
      --success: hsl(152 69% 40%);
      --cyan-dim: hsl(190 100% 50% / 0.1);
      --purple-dim: hsl(247 84% 72% / 0.1);
      --surface-btn-bg: hsl(210 33% 98% / 0.03);
      --surface-btn-border: hsl(210 33% 98% / 0.1);
      --surface-btn-hover: hsl(210 33% 98% / 0.06);
      --surface-btn-border-hover: hsl(190 100% 50% / 0.28);
      --shadow-card: 0 18px 48px hsl(215 25% 10% / 0.4);
      --prose-border: hsl(210 33% 98% / 0.12);
      --prose-border-strong: hsl(210 33% 98% / 0.18);
      --prose-blockquote-border: hsl(247 84% 72% / 0.3);
      --prose-blockquote-bg: hsl(247 84% 72% / 0.1);
      --bg-code: hsl(190 100% 50% / 0.1);
      --bg-pre: hsl(230 22% 12% / 0.92);
      --bg-th: hsl(230 22% 12% / 0.92);
      --toast-bg: hsl(152 69% 40%);
      --toast-fg: hsl(210 33% 98%);
      --icon-bg: hsl(247 84% 72% / 0.1);
      --icon-fg: hsl(247 84% 72%);
      --header-border: hsl(210 33% 98% / 0.1);
      --toast-bg-fail: hsl(349 100% 63%);
    }
  }

  /* ===== Reset & Base ===== */
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    min-height:100vh;
    background:var(--bg);
    color:var(--fg);
    font-family:"Inter","SF Pro Display","Segoe UI",system-ui,-apple-system,BlinkMacSystemFont,"Noto Sans SC",sans-serif;
    line-height:1.5;
    -webkit-font-smoothing:antialiased;
    -moz-osx-font-smoothing:grayscale;
    padding:1.5rem;
  }

  .container{max-width:48rem;margin:0 auto}

  /* ===== Header ===== */
  .header{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:1rem;
    margin-bottom:1.25rem;
    padding-bottom:1rem;
    border-bottom:1px solid var(--header-border);
  }
  .header-left{display:flex;align-items:center;gap:0.75rem;flex:1;min-width:0}
  .header-icon{
    width:2rem;height:2rem;border-radius:0.5rem;
    background:var(--icon-bg);
    display:flex;align-items:center;justify-content:center;
    color:var(--icon-fg);
    flex-shrink:0;
  }
  .header h1{
    font-size:1rem;font-weight:600;color:var(--fg);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  }
  .header .subtitle{
    font-size:0.75rem;color:var(--fg-muted);margin-top:0.125rem;
  }

  /* ===== Action Buttons ===== */
  .actions{display:flex;gap:0.5rem;flex-shrink:0}
  .action-btn{
    display:inline-flex;align-items:center;justify-content:center;
    width:2.5rem;height:2.5rem;border-radius:0.5rem;
    border:1px solid var(--surface-btn-border);
    background:var(--surface-btn-bg);
    box-shadow:inset 0 1px 0 hsl(0 0% 100% / 0.68);
    color:var(--fg-secondary);
    cursor:pointer;
    transition:border-color 0.2s ease,background-color 0.2s ease,color 0.2s ease;
  }
  .action-btn:hover{
    border-color:var(--surface-btn-border-hover);
    background:var(--surface-btn-hover);
    color:var(--fg);
  }
  .action-btn svg{width:1.25rem;height:1.25rem}

  /* ===== Markdown Prose (matching home-markdown-prose from ReportMarkdown.tsx) ===== */
  .markdown{
    line-height:1.6;
    font-size:0.875rem;
    color:var(--fg-secondary);
    white-space:pre-line;
    break-words:break-word;
  }
  /* Headings - match prose-headings:text-foreground prose-headings:font-semibold */
  .markdown h1{
    font-size:1.25rem;
    font-weight:600;
    color:var(--fg);
    margin-top:1rem;
    margin-bottom:0.5rem;
    padding-bottom:0.5rem;
    border-bottom:1px solid var(--prose-border);
  }
  .markdown h2{
    font-size:1.125rem;
    font-weight:600;
    color:var(--purple);
    margin-top:1rem;
    margin-bottom:0.5rem;
  }
  .markdown h3{
    font-size:1rem;
    font-weight:600;
    color:var(--fg);
    margin-top:0.75rem;
    margin-bottom:0.375rem;
  }
  .markdown h4{
    font-size:0.875rem;
    font-weight:600;
    color:var(--fg);
    margin-top:0.5rem;
    margin-bottom:0.25rem;
  }
  /* Paragraphs - match prose-p:leading-relaxed prose-p:mb-3 prose-p:last:mb-0 */
  .markdown p{
    margin:0 0 0.75rem 0;
    line-height:1.625;
  }
  .markdown p:last-child{
    margin-bottom:0;
  }
  /* Lists - match prose-ul:my-2 prose-ol:my-2 prose-li:my-1 */
  .markdown ul,.markdown ol{
    margin:0.5rem 0;
    padding-left:1.5rem;
  }
  .markdown li{
    margin:0.25rem 0;
  }
  /* Blockquotes - match prose-blockquote:text-secondary-text */
  .markdown blockquote{
    border-left:3px solid var(--prose-blockquote-border);
    background:var(--prose-blockquote-bg);
    border-radius:0 0.75rem 0.75rem 0;
    padding:0.5rem 1rem;
    margin:0.75rem 0;
    color:var(--fg-secondary);
    font-style:italic;
  }
  /* Inline code - match prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded */
  .markdown code{
    background:var(--bg-code);
    color:var(--cyan);
    padding:0.125rem 0.375rem;
    border-radius:0.375rem;
    font-size:0.8rem;
  }
  /* Code blocks */
  .markdown pre{
    background:var(--bg-pre);
    border:1px solid var(--prose-border);
    padding:0.75rem 1rem;
    border-radius:0.5rem;
    overflow-x:auto;
    margin:0.75rem 0;
  }
  .markdown pre code{
    background:none;
    padding:0;
    color:var(--fg-secondary);
    font-size:0.8125rem;
  }
  .markdown pre code::before,
  .markdown pre code::after{
    content:none;
  }
  /* Tables - match prose-table:border-collapse */
  .markdown table{
    border-collapse:collapse;
    width:100%;
    margin:0.75rem 0;
    font-size:0.8125rem;
  }
  .markdown th,.markdown td{
    border:1px solid var(--prose-border-strong);
    padding:0.25rem 0.375rem;
    text-align:left;
  }
  .markdown th{
    background:var(--bg-th);
    font-weight:500;
    color:var(--fg);
  }
  .markdown td{
    color:var(--fg-secondary);
  }
  /* Horizontal rule - match prose-hr:my-4 */
  .markdown hr{
    border:none;
    border-top:1px solid var(--prose-border);
    margin:1rem 0;
  }
  /* Strong - match prose-strong:text-foreground prose-strong:font-semibold */
  .markdown strong{
    color:var(--fg);
    font-weight:600;
  }
  /* Links - match prose-a:no-underline hover:prose-a:underline */
  .markdown a{
    color:var(--cyan);
    text-decoration:none;
  }
  .markdown a:hover{
    text-decoration:underline;
  }
  /* Emphasis */
  .markdown em{
    font-style:italic;
  }
  /* Strikethrough (GFM) */
  .markdown del,
  .markdown s{
    text-decoration:line-through;
    color:var(--fg-muted);
  }
  /* Task list items (GFM) */
  .markdown input[type="checkbox"]{
    margin-right:0.375rem;
    accent-color:var(--cyan);
  }

  /* ===== Footer ===== */
  .footer{
    margin-top:1.5rem;padding-top:0.75rem;
    border-top:1px solid var(--header-border);
    text-align:center;color:var(--fg-muted);font-size:0.6875rem;
  }

  /* ===== Toast ===== */
  .toast{
    position:fixed;bottom:1.5rem;left:50%;
    transform:translateX(-50%) translateY(100px);
    background:var(--toast-bg);color:var(--toast-fg);
    padding:0.5rem 1rem;border-radius:0.5rem;
    font-size:0.8125rem;
    transition:transform 0.3s ease;
    z-index:100;
  }
  .toast.show{transform:translateX(-50%) translateY(0)}

  /* ===== Loading / Error ===== */
  .loading{
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:4rem 0;color:var(--fg-muted);
  }
  .spinner{
    width:2.5rem;height:2.5rem;border-radius:9999px;
    border:3px solid var(--border);
    border-top-color:var(--cyan);
    animation:spin 1s linear infinite;
  }
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes fadeIn{from{opacity:0;transform:translateY(0.5rem)}to{opacity:1;transform:translateY(0)}}
  .fade-in{animation:fadeIn 0.3s ease-out}

  /* ===== Responsive ===== */
  @media(max-width:640px){
    body{padding:1rem}
    .header{flex-direction:column;align-items:flex-start}
    .actions{align-self:flex-end}
  }
</style>
"""

    html_head_body = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{display_title} - 分析报告</title>
{css_styles}</head><body>
<div class="container fade-in">
  <div class="header">
    <div class="header-left">
      <div class="header-icon">
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
      </div>
      <div>
        <h1>{display_title}</h1>
        <p class="subtitle">{display_code_date}</p>
      </div>
    </div>
    <div class="actions">
      <!-- Copy Markdown button -->
      <button class="action-btn" onclick="copyMarkdown()" aria-label="复制 Markdown" title="复制 Markdown">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>
      </button>
      <!-- Copy plain text button -->
      <button class="action-btn" onclick="copyPlainText()" aria-label="复制纯文本" title="复制纯文本">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
      </button>
    </div>
  </div>
  <div class="markdown" id="markdown-content">
    <div class="loading"><div class="spinner"></div><p style="margin-top:1rem;font-size:0.875rem">加载中…</p></div>
  </div>
  <div class="footer">由 DSA 每日选股分析系统生成 · 分享链接仅查看此报告</div>
</div>
<div class="toast" id="toast">已复制到剪贴板</div>
"""

    js_html = _SHARE_PAGE_JS.replace("__ENCODED_MARKDOWN__", encoded_markdown)
    return HTMLResponse(content=html_head_body + js_html)
