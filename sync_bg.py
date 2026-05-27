#!/usr/bin/env python3
"""
sync_bg.py — Sincronização de cards em background (roda localmente no Mac).

Uso:
  python3 sync_bg.py              # sync completo (ou retoma checkpoint)
  python3 sync_bg.py --reprocess  # reprocessar evidências com falha
  python3 sync_bg.py --limpar     # apagar checkpoint e começar do zero

Ctrl+C salva posição e para graciosamente. Rode novamente para continuar.
"""
import json
import os
import sys
import time
import signal
import argparse
from datetime import datetime

try:
    import requests
except ImportError:
    print("Dependência ausente. Execute: pip3 install requests")
    sys.exit(1)

BASE_URL = "https://negativacoes-compartilhadas-negativ.vercel.app"
CKPT_FILE = os.path.expanduser("~/.negativacoes_sync_ckpt.json")
DELAY_CARDS = 1.5  # segundos entre cards (throttle para evitar 429 no Groq)

_running = True


def _handle_signal(sig, frame):
    global _running
    _running = False
    print("\n\n⏸  Interrompido — checkpoint salvo. Rode novamente para continuar.", flush=True)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _save_ckpt(data: dict):
    with open(CKPT_FILE, "w") as f:
        json.dump({**data, "saved_at": datetime.now().isoformat()}, f, ensure_ascii=False)


def _load_ckpt() -> dict | None:
    if not os.path.exists(CKPT_FILE):
        return None
    try:
        with open(CKPT_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _clear_ckpt():
    if os.path.exists(CKPT_FILE):
        os.remove(CKPT_FILE)


def _get(path: str) -> dict:
    r = requests.get(f"{BASE_URL}{path}", timeout=90)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict = None) -> dict:
    r = requests.post(f"{BASE_URL}{path}", json=body or {}, timeout=90)
    r.raise_for_status()
    return r.json()


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _scan_all_ids() -> list[str]:
    fases = _get("/admin/sync/fases")["fases"]
    all_ids: list[str] = []
    for fase in fases:
        _log(f"Escaneando: {fase['nome']}...")
        cursor = None
        scanned = matched = 0
        while _running:
            url = f"/admin/sync/scan?phase_id={fase['id']}"
            if cursor:
                url += f"&cursor={cursor}"
            try:
                d = _get(url)
                scanned += d["scanned"]
                matched += d["matched"]
                all_ids.extend(d["matched_ids"])
                if not d["has_next"]:
                    break
                cursor = d["next_cursor"]
            except Exception as e:
                _log(f"  Erro ao escanear {fase['nome']}: {e}")
                break
        label = "cliente×cliente" if fase.get("filtrar_clientes") else "cards"
        _log(f"  ✔ {fase['nome']}: {matched} {label} de {scanned}")
    return all_ids


def _process_loop(all_ids: list[str], start_index: int, prev_erros: int, prev_anexos: int, mode: str):
    erros = prev_erros
    anexos_ok = prev_anexos

    for i in range(start_index, len(all_ids)):
        if not _running:
            _save_ckpt({"all_ids": all_ids, "next_index": i, "erros": erros, "anexos_ok": anexos_ok, "mode": mode})
            return erros, anexos_ok

        card_id = all_ids[i]
        pct = round(i / len(all_ids) * 100)
        _log(f"[{pct}%] {i+1}/{len(all_ids)} | {card_id} | {anexos_ok} evidências | {erros} erros")

        # Passo 1: salvar metadados do card (~2s, sem IA)
        try:
            card_data = _post(f"/admin/process/{card_id}")
            if not card_data.get("ok"):
                erros += 1
                _log(f"  ✗ {card_data.get('error', 'erro ao salvar card')}")
                _save_ckpt({"all_ids": all_ids, "next_index": i + 1, "erros": erros, "anexos_ok": anexos_ok, "mode": mode})
                time.sleep(DELAY_CARDS)
                continue
        except Exception as e:
            erros += 1
            _log(f"  ✗ Erro: {e}")
            _save_ckpt({"all_ids": all_ids, "next_index": i + 1, "erros": erros, "anexos_ok": anexos_ok, "mode": mode})
            time.sleep(DELAY_CARDS)
            continue

        # Passo 2: cada anexo individualmente (~10-20s cada, com Groq)
        for att in (card_data.get("attachments") or []):
            if not _running:
                break
            try:
                d2 = _post("/admin/process-attachment", {
                    "card_id": card_id,
                    "attachment": att,
                    "card_context": card_data["card_context"],
                })
                if d2.get("ok"):
                    anexos_ok += 1
                    _log(f"  ✔ {att.get('filename')} | plataforma: {att.get('plataforma_hint') or '?'}")
                else:
                    _log(f"  ✗ {att.get('filename')}: {d2.get('error', 'erro')}")
            except Exception as e:
                _log(f"  ✗ {att.get('filename')}: {e}")

        _save_ckpt({"all_ids": all_ids, "next_index": i + 1, "erros": erros, "anexos_ok": anexos_ok, "mode": mode})
        if _running:
            time.sleep(DELAY_CARDS)

    return erros, anexos_ok


def main():
    parser = argparse.ArgumentParser(description="Sync de cards em background")
    parser.add_argument("--reprocess", action="store_true", help="Reprocessar evidências com falha")
    parser.add_argument("--limpar", action="store_true", help="Apagar checkpoint e começar do zero")
    args = parser.parse_args()

    if args.limpar:
        _clear_ckpt()
        _log("Checkpoint apagado.")
        if not args.reprocess:
            return

    print("=" * 60)
    print("  Negativações — Sync em Background")
    print("  Ctrl+C para pausar (retoma de onde parou)")
    print("=" * 60)

    if args.reprocess:
        _log("Verificando falhas...")
        try:
            count = _get("/admin/sync/failed-count")
        except Exception as e:
            _log(f"Erro: {e}")
            return
        if count["total_evidencias"] == 0:
            _log("Nenhuma evidência com falha.")
            return
        _log(f"{count['total_evidencias']} falhas em {count['total_cards']} cards.")
        confirm = input("Deletar e reprocessar? [s/N] ").strip().lower()
        if confirm != "s":
            return
        reset = _post("/admin/sync/reset-failed")
        all_ids = reset["card_ids"]
        start_index, prev_erros, prev_anexos, mode = 0, 0, 0, "reprocess"
        _log(f"▶ Reprocessando {len(all_ids)} cards...")
        _save_ckpt({"all_ids": all_ids, "next_index": 0, "erros": 0, "anexos_ok": 0, "mode": mode})
    else:
        ckpt = _load_ckpt()
        if ckpt and ckpt.get("next_index", 0) < len(ckpt.get("all_ids", [])):
            restantes = len(ckpt["all_ids"]) - ckpt["next_index"]
            _log(f"Checkpoint: {restantes} restantes de {len(ckpt['all_ids'])} (salvo em {ckpt.get('saved_at', '?')})")
            confirm = input("Retomar? [S/n] ").strip().lower()
            if confirm != "n":
                all_ids = ckpt["all_ids"]
                start_index = ckpt["next_index"]
                prev_erros = ckpt.get("erros", 0)
                prev_anexos = ckpt.get("anexos_ok", 0)
                mode = ckpt.get("mode", "sync")
                _log(f"▶ Retomando do card {start_index + 1}/{len(all_ids)}...")
            else:
                _clear_ckpt()
                all_ids = _scan_all_ids()
                start_index, prev_erros, prev_anexos, mode = 0, 0, 0, "sync"
                _log(f"▶ Processando {len(all_ids)} cards...")
                _save_ckpt({"all_ids": all_ids, "next_index": 0, "erros": 0, "anexos_ok": 0, "mode": mode})
        else:
            _clear_ckpt()
            all_ids = _scan_all_ids()
            start_index, prev_erros, prev_anexos, mode = 0, 0, 0, "sync"
            _log(f"▶ Processando {len(all_ids)} cards...")
            _save_ckpt({"all_ids": all_ids, "next_index": 0, "erros": 0, "anexos_ok": 0, "mode": mode})

    erros, anexos_ok = _process_loop(all_ids, start_index, prev_erros, prev_anexos, mode)

    if _running:
        _log(f"✅ Concluído! {anexos_ok} evidências salvas, {erros} erros.")
        _clear_ckpt()
    else:
        _log(f"Pausado — {anexos_ok} evidências salvas até agora, {erros} erros.")


if __name__ == "__main__":
    main()
