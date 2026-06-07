"""
ARGO — Test unitari di flotta e model mesh.

Veloci, deterministici, senza rete e senza avviare il server: adatti alla CI.
Blindano due bug corretti nel giugno 2026:
  1. il model mesh assegnava modelli di EMBEDDING ai ruoli di chat;
  2. (a monte) la flotta deve aggregare/deduplicare e degradare con grazia.

Uso:  python test_fleet.py   (esce != 0 se un controllo fallisce)
"""

import fleet
import modelli

_falliti = []


def check(nome, cond, dettaglio=""):
    if not cond:
        _falliti.append(nome)
    print(f"  [{'OK  ' if cond else 'FAIL'}] {nome}{(' :: ' + dettaglio) if dettaglio else ''}")
    return cond


def test_embedding_detection():
    print("test: riconoscimento modelli di embedding")
    for nome in ("bge-m3:latest", "nomic-embed-text:latest", "mxbai-embed-large", "all-minilm"):
        check(f"{nome} = embedding", fleet and modelli._e_modello_embedding(nome))
    for nome in ("qwen2.5:14b-instruct", "llama3.1:8b", "qwen2.5:7b-instruct", "mistral"):
        check(f"{nome} != embedding", not modelli._e_modello_embedding(nome))


def test_taglia():
    print("test: classificazione di taglia")
    check("qwen2.5:14b -> grande", modelli._taglia_modello("qwen2.5:14b-instruct") == "grande")
    check("qwen2.5:7b -> medio", modelli._taglia_modello("qwen2.5:7b-instruct") == "medio")
    check("phi3:mini -> piccolo", modelli._taglia_modello("phi3:mini") == "piccolo")


def test_ruoli_senza_embedding():
    print("test: il mesh non mette embedding nei ruoli di chat")
    installati = [
        "bge-m3:latest", "qwen2.5:14b-instruct", "qwen2.5:7b-instruct",
        "llama3.1:8b", "nomic-embed-text:latest",
    ]
    mesh = modelli.ModelMesh.__new__(modelli.ModelMesh)  # senza __init__/rete
    mesh.host = "http://localhost:11434"
    mesh._livelli = {"riflesso": None, "ragionatore": None, "esperto": None}
    mesh._inizializzato = False
    mesh._errore_init = None
    mesh._pensatore = None
    mesh._get_modelli_installati = lambda: list(installati)  # stub: niente rete
    mesh._rileva_modelli()
    ruoli = mesh._livelli
    for r in ("riflesso", "ragionatore", "esperto"):
        check(f"{r} assegnato", bool(ruoli[r]), str(ruoli[r]))
        check(f"{r} non e' embedding", not modelli._e_modello_embedding(ruoli[r] or ""), str(ruoli[r]))
    check("esperto = modello grande (14b)", ruoli["esperto"] == "qwen2.5:14b-instruct", str(ruoli["esperto"]))


def test_flotta():
    print("test: flotta (normalizzazione, dedup, panoramica vuota)")
    check("normalizza aggiunge schema", fleet._normalizza("127.0.0.1:8773") == "http://127.0.0.1:8773")
    check("normalizza toglie slash finale", fleet._normalizza("http://x:1/") == "http://x:1")
    f = fleet.Flotta(peers=["http://127.0.0.1:8773", "127.0.0.1:8773", "http://127.0.0.1:8774"])
    check("dedup peer", len(f.peers) == 2, str(f.peers))
    vuota = fleet.Flotta(peers=[]).panoramica()
    check("panoramica vuota = zeri", vuota["totale"] == 0 and vuota["online"] == 0)


def main():
    test_embedding_detection()
    test_taglia()
    test_ruoli_senza_embedding()
    test_flotta()
    print()
    if _falliti:
        print(f"[TEST] FALLITI: {len(_falliti)} -> {', '.join(_falliti)}")
        raise SystemExit(1)
    print("[TEST] TUTTI I CONTROLLI SUPERATI")


if __name__ == "__main__":
    main()
