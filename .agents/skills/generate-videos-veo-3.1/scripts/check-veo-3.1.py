# -*- coding: utf-8 -*-
"""
Script kiểm tra môi trường, cấu hình GEMINI_API_KEY và quyền truy cập mô hình Veo 3.1
(veo-3.1-generate-preview & veo-3.1-fast-generate-preview) trong Gemini API.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

VEO_MODELS = [
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
]
MOLTBOT_JSON = os.path.expanduser(r"~\.clawdbot\moltbot.json")


def mask_key(k: str) -> str:
    if not k or len(k) < 8:
        return "***"
    return f"{k[:4]}***{k[-4:]}"


def find_api_key(explicit_key: str = "") -> tuple[str, str]:
    """Tìm API Key từ nhiều nguồn: CLI -> ENV -> .env -> Moltbot config."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip(), "CLI Argument (--api-key)"

    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val, f"Environment Variable ({env_name})"

    # Tìm trong .env ở thư mục hiện tại và các thư mục cha
    cwd = Path.cwd()
    search_dirs = [cwd, *cwd.parents, Path(__file__).resolve().parent.parent]
    for d in search_dirs:
        env_path = d / ".env"
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                            _, v = line.split("=", 1)
                            v = v.strip().strip("'\"")
                            if v:
                                return v, f".env file ({env_path})"
            except Exception:
                pass

    if os.path.isfile(MOLTBOT_JSON):
        try:
            with open(MOLTBOT_JSON, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            nb = cfg.get("skills", {}).get("generate-videos-veo-3-1", {}) or cfg.get("skills", {}).get("nano-banana-pro", {})
            key = nb.get("apiKey") or nb.get("env", {}).get("GEMINI_API_KEY")
            if key and str(key).strip():
                return str(key).strip(), f"Moltbot Config ({MOLTBOT_JSON})"
        except Exception:
            pass

    return "", "None"


def check_sdk_available() -> tuple[bool, str]:
    try:
        import google.genai
        from google.genai import types
        ver = getattr(google.genai, "__version__", "installed")
        return True, f"google-genai ({ver})"
    except ImportError:
        return False, "Not installed (pip install google-genai)"


def verify_model_rest(model_id: str, api_key: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}?key={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "Veo3-Checker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "model": model_id,
                "status": "OK",
                "displayName": data.get("displayName", model_id),
                "description": data.get("description", ""),
                "supportedGenerationMethods": data.get("supportedGenerationMethods", []),
            }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {
            "model": model_id,
            "status": f"HTTP {e.code}",
            "error": err_msg,
        }
    except Exception as e:
        return {
            "model": model_id,
            "status": "Error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra trạng thái skill Veo 3.1 & Gemini API")
    parser.add_argument("--api-key", default="", help="Khóa API Gemini cần kiểm tra")
    parser.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON thuần")
    args = parser.parse_args()

    sdk_ok, sdk_info = check_sdk_available()
    api_key, key_source = find_api_key(args.api_key)

    model_results = []
    if api_key:
        for m in VEO_MODELS:
            res = verify_model_rest(m, api_key)
            model_results.append(res)

    all_ok = bool(api_key and any(r.get("status") == "OK" for r in model_results))

    result = {
        "ok": all_ok,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "sdk_installed": sdk_ok,
        "sdk_info": sdk_info,
        "api_key_found": bool(api_key),
        "api_key_masked": mask_key(api_key) if api_key else None,
        "api_key_source": key_source,
        "models": model_results,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if all_ok else 1

    print("=" * 60)
    print("🔍 KIỂM TRA TRẠNG THÁI SKILL: GENERATE VIDEOS WITH VEO 3.1")
    print("=" * 60)
    print(f"• Python Version : {result['python_version']} ({result['platform']})")
    print(f"• GenAI SDK      : {sdk_info} {'[✓]' if sdk_ok else '[!]'}")
    print(f"• Gemini API Key : {result['api_key_masked'] or 'CHƯA TÌM THẤY'} ({key_source})")
    print("-" * 60)
    print("📋 TRẠNG THÁI MÔ HÌNH VEO 3.1:")

    if not api_key:
        print("  ❌ Không có API Key để kiểm tra trạng thái mô hình.")
        print("  👉 Vui lòng cấu hình GEMINI_API_KEY trong .env hoặc biến môi trường.")
    else:
        for m in model_results:
            icon = "✓" if m.get("status") == "OK" else "✗"
            print(f"  [{icon}] {m['model']}")
            if m.get("status") == "OK":
                print(f"      Display Name : {m.get('displayName')}")
                print(f"      Methods      : {', '.join(m.get('supportedGenerationMethods', []))}")
            else:
                print(f"      Lỗi          : {m.get('status')} - {m.get('error', '')[:100]}")

    print("=" * 60)
    if all_ok:
        print("✅ HỆ THỐNG SẴN SÀNG TẠO VIDEO VỚI VEO 3.1!")
    else:
        print("⚠️ CẦN HOÀN TẤT THIẾT LẬP TRƯỚC KHI TẠO VIDEO.")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
