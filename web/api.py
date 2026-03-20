import os
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from config import Config
from services.announce_service import get_announcements
from services.usage_service import (
    get_participant_by_token,
    submit_usage,
    get_leaderboard,
    get_usage_summary,
    auto_register,
)

api_router = APIRouter(prefix="/api")


# ──────────────────────────────────────
# 기존 API
# ──────────────────────────────────────

@api_router.get("/status")
async def get_status():
    """캠프 현황 API."""
    return {
        "camp_name": Config.CAMP_NAME,
        "camp_day": Config.camp_day(),
        "days_remaining": Config.days_remaining(),
        "progress": round(Config.progress_percent(), 1),
        "start_date": str(Config.CAMP_START_DATE),
        "end_date": str(Config.CAMP_END_DATE),
    }


@api_router.get("/announcements")
async def list_announcements(limit: int = 20):
    """공지 목록 API."""
    announcements = get_announcements(limit=limit)
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "channel": a.channel,
            "is_sent": a.is_sent,
            "sent_at": str(a.sent_at) if a.sent_at else None,
            "created_at": str(a.created_at),
        }
        for a in announcements
    ]


# ──────────────────────────────────────
# 사용량 추적 API
# ──────────────────────────────────────

def _get_base_url(request: Request) -> str:
    """요청에서 base URL을 추출합니다."""
    forwarded = request.headers.get("x-forwarded-proto")
    scheme = forwarded or request.url.scheme
    return f"{scheme}://{request.url.netloc}"


@api_router.get("/setup", response_class=PlainTextResponse)
async def setup_script(request: Request):
    """참가자 셋업 스크립트를 반환합니다."""
    base_url = _get_base_url(request)
    script = f'''#!/bin/bash
set -e

API_URL="{base_url}"
CONFIG_DIR="$HOME/.config/sentbe-camp"

# 토큰 인자 확인
TOKEN="${{1:-}}"

# 이미 설정되어 있으면 스킵
if [ -f "$CONFIG_DIR/token" ]; then
  echo "✅ 이미 설정되어 있습니다!"
  echo "  토큰: $CONFIG_DIR/token"
  echo "  훅: ~/.claude/settings.json (Stop hook)"
  echo ""
  echo "재설정하려면 rm -rf $CONFIG_DIR 후 다시 실행하세요."
  exit 0
fi

echo ""
echo "🧙‍♂️ {Config.CAMP_NAME} 리더보드 설정"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 토큰이 없으면 이름으로 등록
if [ -z "$TOKEN" ]; then
  read -p "📝 이름을 입력하세요: " NAME
  if [ -z "$NAME" ]; then
    echo "❌ 이름은 필수입니다."
    echo "💡 또는 대시보드에서 Google 로그인 후 개인 토큰이 포함된 명령어를 복사하세요."
    exit 1
  fi

  echo ""
  echo "등록 중..."

  RESPONSE=$(curl -sf -X POST "$API_URL/api/usage/register" \\
    -H "Content-Type: application/json" \\
    -d "{{\\"name\\": \\"$NAME\\"}}")

  TOKEN=$(echo "$RESPONSE" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>console.log(JSON.parse(d).token))" 2>/dev/null)

  if [ -z "$TOKEN" ]; then
    echo "❌ 등록에 실패했습니다. 서버 연결을 확인해주세요."
    exit 1
  fi
fi

# 3. 토큰 저장
mkdir -p "$CONFIG_DIR"
echo "$TOKEN" > "$CONFIG_DIR/token"
chmod 600 "$CONFIG_DIR/token"
echo "$API_URL" > "$CONFIG_DIR/api_url"

# 4. Hook 스크립트 다운로드
curl -sf "$API_URL/api/hook-script" -o "$CONFIG_DIR/report-usage.js.tmp"
if [ -s "$CONFIG_DIR/report-usage.js.tmp" ]; then
  mv "$CONFIG_DIR/report-usage.js.tmp" "$CONFIG_DIR/report-usage.js"
else
  rm -f "$CONFIG_DIR/report-usage.js.tmp"
  echo "❌ Hook 스크립트 다운로드 실패"
  exit 1
fi

# 5. Claude Code Stop hook 등록
SETTINGS_FILE="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
if [ ! -f "$SETTINGS_FILE" ]; then
  echo '{{}}' > "$SETTINGS_FILE"
fi

node -e "
const fs = require('fs');
const f = '$SETTINGS_FILE';
const s = JSON.parse(fs.readFileSync(f, 'utf8'));
if (!s.hooks) s.hooks = {{}};
if (!s.hooks.Stop) s.hooks.Stop = [];
const idx = s.hooks.Stop.findIndex(h => h.hooks && h.hooks.some(hh => hh.command && hh.command.includes('sentbe-camp/report-usage')));
if (idx >= 0) {{
  s.hooks.Stop[idx].matcher = '.*';
}} else {{
  const hookPath = require('path').join(require('os').homedir(), '.config', 'sentbe-camp', 'report-usage.js');
  s.hooks.Stop.push({{ matcher: '.*', hooks: [{{ type: 'command', command: 'node ' + hookPath }}] }});
}}
fs.writeFileSync(f, JSON.stringify(s, null, 2));
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ $NAME님, 등록 완료!"
echo ""
echo "  Claude Code를 쓰면 사용량이"
echo "  자동으로 리더보드에 반영됩니다."
echo ""
echo "  🏆 리더보드: $API_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
'''
    return script


@api_router.get("/hook-script", response_class=PlainTextResponse)
async def hook_script():
    """Claude Code Stop hook JS 스크립트를 반환합니다."""
    return '''const fs = require("fs");
const path = require("path");
const os = require("os");
const https = require("https");
const http = require("http");

const HARD_TIMEOUT = setTimeout(() => process.exit(0), 5000);
HARD_TIMEOUT.unref();

const PRICING = {
  "claude-opus-4-6":   { input: 15, output: 75, cache_write: 18.75, cache_read: 1.50 },
  "claude-sonnet-4-6": { input: 3, output: 15, cache_write: 3.75, cache_read: 0.30 },
  "claude-haiku-4-5":  { input: 0.80, output: 4, cache_write: 1, cache_read: 0.08 },
};

function getPrice(model) {
  if (!model) return PRICING["claude-sonnet-4-6"];
  for (const [key, price] of Object.entries(PRICING))
    if (model.includes(key)) return price;
  if (model.includes("opus")) return PRICING["claude-opus-4-6"];
  if (model.includes("haiku")) return PRICING["claude-haiku-4-5"];
  return PRICING["claude-sonnet-4-6"];
}

function getSessionCachePath() {
  return path.join(os.homedir(), ".config", "sentbe-camp", "session-cache.json");
}
function loadSessionCache() {
  try { return JSON.parse(fs.readFileSync(getSessionCachePath(), "utf8")); } catch { return {}; }
}
function saveSessionCache(cache) {
  try {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    for (const [k, v] of Object.entries(cache)) if (v.ts && v.ts < cutoff) delete cache[k];
    fs.writeFileSync(getSessionCachePath(), JSON.stringify(cache));
  } catch {}
}

function httpPost(apiUrl, token, data, timeoutMs, cb) {
  try {
    const url = new URL(apiUrl + "/api/usage/submit");
    const mod = url.protocol === "https:" ? https : http;
    const req = mod.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      timeout: timeoutMs,
    }, (res) => { res.on("data", () => {}); res.on("end", () => cb(res.statusCode >= 200 && res.statusCode < 300)); });
    req.on("timeout", () => { req.destroy(); cb(false); });
    req.on("error", () => cb(false));
    req.write(data);
    req.end();
  } catch { cb(false); }
}

let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  try {
    const event = JSON.parse(input);
    const transcriptPath = event.transcript_path;
    const sessionId = event.session_id;
    if (!transcriptPath || !fs.existsSync(transcriptPath)) process.exit(0);

    const configDir = path.join(os.homedir(), ".config", "sentbe-camp");
    const token = fs.readFileSync(path.join(configDir, "token"), "utf8").trim();
    const apiUrl = fs.readFileSync(path.join(configDir, "api_url"), "utf8").trim();

    const lines = fs.readFileSync(transcriptPath, "utf8").split("\\n").filter(Boolean);
    let totalInput = 0, totalOutput = 0, totalCacheCreate = 0, totalCacheRead = 0, totalCost = 0;
    const modelsSet = new Set();

    for (const line of lines) {
      try {
        const entry = JSON.parse(line);
        if (entry.type !== "assistant") continue;
        const usage = entry.message && entry.message.usage;
        const model = entry.message && entry.message.model;
        if (usage) {
          const inp = usage.input_tokens || 0, out = usage.output_tokens || 0;
          const cw = usage.cache_creation_input_tokens || 0, cr = usage.cache_read_input_tokens || 0;
          totalInput += inp; totalOutput += out; totalCacheCreate += cw; totalCacheRead += cr;
          const p = getPrice(model);
          totalCost += (inp * p.input + out * p.output + cw * p.cache_write + cr * p.cache_read) / 1000000;
        }
        if (model) modelsSet.add(model);
      } catch {}
    }

    const totalTokens = totalInput + totalOutput + totalCacheCreate + totalCacheRead;
    if (totalTokens === 0) process.exit(0);

    const cache = loadSessionCache();
    const prev = (sessionId && cache[sessionId]) || { inp: 0, out: 0, cw: 0, cr: 0, cost: 0, n: 0 };
    const dI = Math.max(0, totalInput - prev.inp);
    const dO = Math.max(0, totalOutput - prev.out);
    const dCW = Math.max(0, totalCacheCreate - prev.cw);
    const dCR = Math.max(0, totalCacheRead - prev.cr);
    const dCost = Math.max(0, totalCost - prev.cost);
    const dTotal = dI + dO + dCW + dCR;
    if (dTotal <= 0) process.exit(0);

    if (sessionId) {
      cache[sessionId] = { inp: totalInput, out: totalOutput, cw: totalCacheCreate, cr: totalCacheRead, cost: totalCost, n: prev.n + 1, ts: Date.now() };
      saveSessionCache(cache);
    }

    const submissionId = sessionId ? (prev.n > 0 ? sessionId + "_r" + prev.n : sessionId) : null;
    const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
    const data = JSON.stringify({
      session_id: submissionId, date: today,
      input_tokens: dI, output_tokens: dO,
      cache_creation_tokens: dCW, cache_read_tokens: dCR,
      total_tokens: dTotal, total_cost: Math.round(dCost * 100) / 100,
      models_used: Array.from(modelsSet),
    });

    httpPost(apiUrl, token, data, 3000, () => process.exit(0));
  } catch { process.exit(0); }
});
'''


@api_router.post("/usage/register")
async def usage_register(request: Request):
    """이름으로 자동 등록하고 토큰을 발급합니다."""
    data = await request.json()
    name = data.get("name", "").strip()
    team = data.get("team", "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    result = auto_register(name, team)
    return result


@api_router.post("/usage/onboard")
async def usage_onboard(authorization: str = Header(None)):
    """리더보드 온보딩 (토큰 유효성 확인)."""
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    token = authorization.split(" ", 1)[1]
    participant = get_participant_by_token(token)
    if not participant:
        return JSONResponse({"error": "invalid token"}, status_code=401)
    return {"ok": True, "name": participant.name}


@api_router.post("/usage/submit")
async def usage_submit(request: Request, authorization: str = Header(None)):
    """사용량 데이터를 수신합니다."""
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    token = authorization.split(" ", 1)[1]
    participant = get_participant_by_token(token)
    if not participant:
        return JSONResponse({"error": "invalid token"}, status_code=401)

    data = await request.json()
    submit_usage(participant.id, data)
    return {"ok": True}


@api_router.get("/usage/leaderboard")
async def usage_leaderboard(date: Optional[str] = None):
    """리더보드 API."""
    return get_leaderboard(date_filter=date)
