"""
XAUUSD Analyst Bot v13 — FastAPI Backend
Jalankan: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Endpoint:
  GET  /api/analysis          → data analisis lengkap
  GET  /api/signal/limit      → signal limit terkini
  GET  /api/signal/breakout   → signal breakout terkini
  GET  /api/history           → riwayat signal
  GET  /api/active            → signal aktif
  GET  /api/settings          → settings saat ini
  POST /api/settings          → update settings
  POST /api/subscribe         → simpan push subscription
  POST /api/push/test         → test push notifikasi ke semua subscriber
"""

import sys, os, json, time, asyncio, requests as _req
import ssl
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

# ── SSL Fix: bypass SSL verification issues ──
ssl._create_default_https_context = ssl._create_unverified_context

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# ── Import dari bot utama ──
# Pastikan rcai_v13.py ada di direktori yang sama atau di sys.path
BOT_DIR = Path(__file__).parent.parent  # sesuaikan jika perlu
sys.path.insert(0, str(BOT_DIR))

try:
    import rcai_v13 as bot
    BOT_OK = True
except ImportError as e:
    print(f"[WARNING] Tidak bisa import rcai_v13: {e}")
    BOT_OK = False

# ── Telegram Auto Notif ──
TG_TOKEN    = "8532798713:AAEaA7OwliA1KH8QeBSuQRn8DmafwQ2a3PE"
TG_OWNER_ID = "7822832986"
TG_CHANNEL  = "@RC_Community_FX"

def tg_send(chat_id: str, text: str):
    """Kirim pesan ke Telegram (owner atau channel)."""
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        _req.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"[TG] Gagal kirim: {e}")

def tg_notify_signal(a: dict):
    """Format dan kirim signal VALID/SNIPER ke Telegram."""
    tier    = a.get("tier", "B")
    dirn    = a.get("direction", "?")
    tick    = a.get("tick", 0)
    score   = a.get("zone_tier_lmt", {}).get("score_pct", 0)
    session = a.get("session", "?")
    sig     = a.get("signal_lmt") or a.get("signal_bkout") or {}

    isBuy   = dirn == "Buy"
    dir_ico = "🟢" if isBuy else "🔴"
    tier_ico= "🎯 SNIPER" if tier == "S" else "✅ VALID"
    rr_best = sig.get("rr2") or sig.get("rr1") or "?"

    lines = [
        f"\u25aa\ufe0f XAUUSD \u00b7 {dir_ico} {dirn} {sig.get('order_type','')}",
        f"\u25aa\ufe0f {session} Session \u00b7 {score}% {tier_ico}",
        "",
        f"\u25ce Entry  {sig.get('entry_lo','?')} \u2013 {sig.get('entry_hi','?')}",
        f"\u25ce SL     {sig.get('sl','?')}",
        f"\u25cf TP1    {sig.get('tp1','?')}",
        f"\u25cf TP2    {sig.get('tp2','?')}",
        f"\u25cf TP3    {sig.get('tp3','?')}",
        "",
        f"\u25b8 Lot {sig.get('lot','?')} \u00b7 RR 1:{rr_best}",
        "",
        "<i>RC AI TRADER \u00b7 Ril Bahry</i>"
    ]
    msg = "\n".join(lines)

    # Kirim ke owner DM
    tg_send(TG_OWNER_ID, msg)
    # Kirim ke channel
    tg_send(TG_CHANNEL, msg)
    print(f"[TG] Signal {tier} {dirn} dikirim ke Telegram")

# ── Simpan push subscriptions ──
SUBS_FILE = Path(__file__).parent / "subscriptions.json"

def load_subs():
    if SUBS_FILE.exists():
        try:
            return json.loads(SUBS_FILE.read_text())
        except:
            return []
    return []

def save_subs(subs):
    SUBS_FILE.write_text(json.dumps(subs, indent=2))

subscriptions: list = load_subs()

# ── FastAPI app ──
app = FastAPI(title="XAUUSD Analyst API v13", version="13.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (PWA) ──
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ──────────────────────────────────────────────
# Helper: serialisasi data bot ke JSON-safe dict
# ──────────────────────────────────────────────
def make_json_safe(obj):
    """Rekursif konversi tuple/set/non-serializable ke JSON-safe."""
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(i) for i in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)

def get_analysis_json(force: bool = False) -> dict:
    if not BOT_OK:
        return {"error": "Bot module tidak tersedia", "demo": True, **demo_data()}
    try:
        a = bot.run_analysis(force=force)
        if not a:
            return {"error": "Data tidak tersedia dari API"}
        return make_json_safe(a)
    except Exception as e:
        return {"error": str(e)}

def demo_data() -> dict:
    """Fallback data demo kalau bot tidak bisa diimport."""
    return {
        "tick": 3325.50,
        "direction": "Buy",
        "tier": "A",
        "tier_desc": "✅ VALID - Konfluensi Cukup, Entry OK",
        "confidence": 62,
        "smc_score": 71,
        "trend_strength": "Moderate",
        "session": "London",
        "tradeable": True,
        "timeframe": "15min",
        "atr": 4.2,
        "rsi": 52.3,
        "macd": [0.12, 0.08, 0.04],
        "adx": [28.1, 32.5, 18.3],
        "stoch": [62.1, 58.4],
        "bb": [3330.0, 3325.0, 3320.0],
        "williams": -38.5,
        "cci": 45.2,
        "vwap": 3323.8,
        "patterns": ["Bullish Pin Bar"],
        "support": [3318.5, 3312.0, 3305.5],
        "resistance": [3332.0, 3338.5, 3345.0],
        "pivots": {"P": 3325.0, "R1": 3333.0, "R2": 3341.0, "R3": 3349.0,
                   "S1": 3317.0, "S2": 3309.0, "S3": 3301.0},
        "signal_lmt": {
            "direction": "Buy", "entry_lo": 3318.5, "entry_hi": 3320.0,
            "entry_mid": 3319.25, "entry_src": "OB", "order_type": "Buy Limit",
            "sl": 3312.5, "sl_method": "Swing Low", "risk": 6.75,
            "tp1": 3332.0, "tp2": 3338.5, "tp3": 3345.0,
            "rr1": 1.9, "rr2": 2.9, "rr3": 3.8, "atr": 4.2, "lot": 0.05
        },
        "signal_bkout": {
            "direction": "Buy", "entry_lo": 3332.0, "entry_hi": 3332.5,
            "entry_mid": 3332.25, "entry_src": "Breakout BOS", "order_type": "Buy Stop",
            "sl": 3324.0, "sl_method": "ATR", "risk": 8.25,
            "tp1": 3345.0, "tp2": 3352.0, "tp3": 3360.0,
            "rr1": 1.5, "rr2": 2.4, "rr3": 3.3, "atr": 4.2, "lot": 0.04
        },
        "lmt_ok": True, "bkout_ok": False,
        "zone_tier_lmt": {
            "tier": "A", "score_pct": 62, "score": 70, "execute": True,
            "pass_list": ["HTF Trend 2/3 TF OK", "BOS 3318.5", "OB 3316-3319 (78%)", "Fib Zone 61.8%"],
            "fail_list": ["Belum ada Liq Sweep", "Tidak ada FVG"],
        },
        "checklist_lmt": {
            "liq_sweep_ok": False, "flip_ok": True, "at_zone": True,
            "ob_ok": True, "fvg_ok": False, "fib_zone_ok": True, "fib_conf_ok": False,
            "bos_ok": True, "htf_trend_ok": True, "htf_trend_strong": False, "htf_bull_n": 2,
            "rr_ok": True, "candle_ok": True, "indicators_ok": True,
            "rsi_ok": True, "adx_ok": True, "macd_ok": True, "rsi_v": 52.3, "adx_v": 28.1,
            "sd_ok": True, "sd_label": "Demand DBR 3316-3320 Q:78% FRESH",
            "sr_ok": True, "sr_at_zone": True, "sr_label": "SUP 3318.5 str:72% touch:3x AT ZONE",
            "liq_label": "-", "flip_label": "RBS @ 3318.5", "ob_label": "OB 3316-3319 (78%)",
            "fvg_label": "-", "fib_label": "Fib 61.8% 62.3% Premium Fib Zone",
            "bos_label": "BOS 3318.5", "patterns": ["Bullish Pin Bar"],
        },
        "smc_bos": {"structure": "Bullish", "hh": True, "hl": True, "lh": False, "ll": False,
                    "bos": True, "bos_level": 3318.5, "choch": False, "mss": False},
        "smc_obs": [{"ob_lo": 3316.0, "ob_hi": 3319.0, "ob_mid": 3317.5, "strength": 78}],
        "smc_fvgs": [],
        "smc_liq": {"sweep_bull": False, "sweep_bear": False, "eqh_zones": [3332.0], "eql_zones": [3312.0]},
        "fib_htf": {"valid": True, "fib_pct": 62.3, "zone": "Premium Fib Zone",
                    "nearest_label": "61.8%", "nearest_price": 3318.2, "confluence": True,
                    "swing_high": 3345.0, "swing_low": 3295.0,
                    "fib_50": 3320.0, "fib_618": 3318.2, "fib_705": 3315.8, "fib_79": 3313.5},
        "rbs_sbr": {"rbs_confirmed": True, "sbr_confirmed": False, "at_rbs": True,
                    "nearest_rbs": {"level": 3318.5, "dist": 1.0}, "flip_type": "RBS", "flip_level": 3318.5},
        "sd_zones": {
            "near_demand": {"zone_lo": 3316.0, "zone_hi": 3320.0, "quality": 78, "fresh": True,
                            "tests": 0, "at_zone": True, "is_4h_conf": True},
            "sd_ok_buy": True, "sd_ok_sell": False,
        },
        "sr_detail": {
            "support_zones": [{"level": 3318.5, "touches": 3, "strength": 72, "at_zone": True, "dist": 1.0}],
            "resistance_zones": [{"level": 3332.0, "touches": 2, "strength": 58, "at_zone": False, "dist": 6.5}],
            "near_support": {"level": 3318.5, "strength": 72},
            "near_resistance": {"level": 3332.0, "strength": 58},
        },
        "is_fake": False, "fake_reasons": [], "rr_valid": True,
        "lmt_pass": ["BOS/CHoCH OK", "OB Ada", "Fib Zone Valid"],
        "lmt_fail": ["Liq Sweep belum ada"],
    }

# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────

@app.get("/")
async def index():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"status": "XAUUSD API v13 running", "docs": "/docs"}

@app.get("/api/analysis")
async def api_analysis(force: bool = False):
    return JSONResponse(get_analysis_json(force=force))

@app.get("/api/signal/limit")
async def api_signal_limit():
    a = get_analysis_json()
    if "error" in a and "signal_lmt" not in a:
        raise HTTPException(502, a["error"])
    return JSONResponse({
        "signal": a.get("signal_lmt"),
        "tier": a.get("tier"),
        "score_pct": a.get("zone_tier_lmt", {}).get("score_pct", 0),
        "execute": a.get("lmt_ok", False),
        "pass_list": a.get("lmt_pass", []),
        "fail_list": a.get("lmt_fail", []),
        "checklist": a.get("checklist_lmt", {}),
    })

@app.get("/api/signal/breakout")
async def api_signal_breakout():
    a = get_analysis_json()
    if "error" in a and "signal_bkout" not in a:
        raise HTTPException(502, a.get("error", "Error"))
    return JSONResponse({
        "signal": a.get("signal_bkout"),
        "tier": a.get("tier"),
        "score_pct": a.get("zone_tier_bkout", {}).get("score_pct", 0),
        "execute": a.get("bkout_ok", False),
        "pass_list": a.get("bkout_pass", []),
        "fail_list": a.get("bkout_fail", []),
    })

@app.get("/api/history")
async def api_history():
    if not BOT_OK:
        return JSONResponse({"history": [], "stats": {}})
    try:
        h = bot.load_history()
        total = len(h)
        wins  = sum(1 for x in h if x.get("result") in ("TP1","TP2","TP3"))
        be    = sum(1 for x in h if x.get("result") == "BE")
        loss  = sum(1 for x in h if x.get("result") == "SL")
        return JSONResponse({
            "history": make_json_safe(h[-20:]),
            "stats": {"total": total, "wins": wins, "be": be, "loss": loss,
                      "wr": round(wins/total*100, 1) if total else 0}
        })
    except Exception as e:
        return JSONResponse({"history": [], "error": str(e)})

@app.get("/api/active")
async def api_active():
    if not BOT_OK:
        return JSONResponse({"signals": []})
    return JSONResponse({"signals": make_json_safe(bot.active_signals)})

@app.get("/api/settings")
async def api_settings():
    if not BOT_OK:
        return JSONResponse({})
    return JSONResponse(make_json_safe(bot.USER_SETTINGS))

@app.post("/api/settings")
async def api_settings_update(request: Request):
    if not BOT_OK:
        raise HTTPException(503, "Bot tidak tersedia")
    body = await request.json()
    for k, v in body.items():
        if k in bot.USER_SETTINGS:
            bot.USER_SETTINGS[k] = v
    bot.save_settings(bot.USER_SETTINGS)
    bot._cache = None
    return JSONResponse({"ok": True, "settings": make_json_safe(bot.USER_SETTINGS)})

@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    """Simpan push subscription dari browser."""
    body = await request.json()
    endpoint = body.get("endpoint", "")
    if not endpoint:
        raise HTTPException(400, "Endpoint wajib ada")
    # Cek duplikat
    global subscriptions
    existing = [s for s in subscriptions if s.get("endpoint") != endpoint]
    existing.append(body)
    subscriptions = existing
    save_subs(subscriptions)
    return JSONResponse({"ok": True, "count": len(subscriptions)})

@app.delete("/api/subscribe")
async def api_unsubscribe(request: Request):
    body = await request.json()
    endpoint = body.get("endpoint", "")
    global subscriptions
    subscriptions = [s for s in subscriptions if s.get("endpoint") != endpoint]
    save_subs(subscriptions)
    return JSONResponse({"ok": True})

@app.post("/api/share")
async def api_share(request: Request):
    """Terima teks analisa/signal dari frontend dan kirim ke channel Telegram."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    kind = body.get("kind", "manual")

    if not text:
        raise HTTPException(400, "text kosong")

    try:
        tg_send(TG_CHANNEL, text)
        print(f"[Share] '{kind}' dikirim ke {TG_CHANNEL}")
        return JSONResponse({"ok": True, "kind": kind})
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/favicon.ico")
async def favicon():
    fav = STATIC_DIR / "favicon.ico"
    if fav.exists():
        return FileResponse(str(fav))
    # fallback ke rc-logo.jpg jika favicon.ico tidak ada
    fav2 = STATIC_DIR / "icons" / "rc-logo.jpg"
    if fav2.exists():
        return FileResponse(str(fav2))
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/icons/{filename}")
async def serve_icon(filename: str):
    from fastapi.responses import Response
    icon_path = STATIC_DIR / "icons" / filename
    if icon_path.exists():
        return FileResponse(str(icon_path))
    return Response(status_code=204)

@app.get("/api/ping")
async def ping():
    return {"status": "ok", "ts": int(time.time()), "bot_ok": BOT_OK}

# ── Background: kirim push notif saat signal valid ──
_last_push_tier = "B"
_last_push_ts   = 0

async def push_loop():
    """Loop background — cek analisis setiap 5 menit, kirim push kalau tier naik ke A/S."""
    global _last_push_tier, _last_push_ts
    await asyncio.sleep(30)  # tunggu startup
    while True:
        try:
            a = get_analysis_json(force=True)
            tier      = a.get("tier", "B")
            score_pct = a.get("zone_tier_lmt", {}).get("score_pct", 0)
            tick      = a.get("tick", 0)
            dirn      = a.get("direction", "")
            exec_ok   = a.get("lmt_ok", False)
            now_ts    = time.time()

            # Kirim push hanya jika: tier A/S, execute OK, cooldown 30 menit
            should_push = (
                tier in ("S", "A") and
                exec_ok and
                (tier != _last_push_tier or now_ts - _last_push_ts > 1800)
            )

            if should_push:
                # ── Kirim notifikasi Telegram ──
                tg_notify_signal(a)
                tier_lbl = "🎯 SNIPER" if tier == "S" else "✅ VALID"
                sig = a.get("signal_lmt", {})
                notif_payload = {
                    "title": f"XAUUSD Signal {dirn} — {tier_lbl}",
                    "body": (
                        f"Score: {score_pct}% | Price: {tick}\n"
                        f"Entry: {sig.get('entry_lo','?')}–{sig.get('entry_hi','?')}\n"
                        f"SL: {sig.get('sl','?')} | TP1: {sig.get('tp1','?')}"
                    ),
                    "tier": tier,
                    "score": score_pct,
                    "direction": dirn,
                }
                # Web Push kirim lewat pywebpush jika tersedia
                try:
                    from pywebpush import webpush, WebPushException
                    VAPID_PRIVATE = os.getenv("VAPID_PRIVATE_KEY", "")
                    VAPID_EMAIL   = os.getenv("VAPID_EMAIL", "mailto:admin@xaubot.local")
                    if VAPID_PRIVATE:
                        for sub in subscriptions:
                            try:
                                webpush(
                                    subscription_info=sub,
                                    data=json.dumps(notif_payload),
                                    vapid_private_key=VAPID_PRIVATE,
                                    vapid_claims={"sub": VAPID_EMAIL},
                                )
                            except WebPushException as e:
                                print(f"[Push] {e}")
                except ImportError:
                    print(f"[Push] pywebpush tidak tersedia — install: pip install pywebpush")

                _last_push_tier = tier
                _last_push_ts   = now_ts
                print(f"[Push] Notif dikirim: {tier} {dirn} score={score_pct}%")

        except Exception as e:
            print(f"[PushLoop] {e}")

        await asyncio.sleep(300)  # 5 menit

@app.on_event("startup")
async def startup():
    asyncio.create_task(push_loop())
    print("✅ XAUUSD API Server v13 siap")
    print(f"   Bot module: {'OK' if BOT_OK else 'DEMO MODE'}")
    print(f"   Subscribers: {len(subscriptions)}")
