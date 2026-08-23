#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026-08-24 EKLENTİSİ: PreToolUse kancası -- backend/.env dosyasının
(gerçek sırlar: Render API anahtarı, admin şifresi, Sentry/B2 token'ları
burada duruyor) yanlışlıkla ya da bilerek gitignore'u BYPASS ederek
(force ile) git'e eklenmesini/commit edilmesini engeller.

.gitignore zaten NORMAL `git add`'i engelliyor (bkz. .gitignore'daki
"backend/.env" satırı) -- bu kanca sadece `-f`/`--force` ile o korumayı
bilerek aşma ihtimaline karşı İKİNCİ bir savunma katmanı (defense in
depth). Tek başına yeterli değil, gitignore'un yedeği.

Claude Code hook sözleşmesi: exit code 2 = araç çağrısını ENGELLE,
stderr'e yazılan mesaj Claude'a geri bildirilir. exit code 0 = izin ver.
"""
import json
import re
import sys

try:
    veri = json.load(sys.stdin)
except Exception:
    # Girdi ayrıştırılamazsa engelleme -- sessizce çalışmaya devam etsin
    # (bu kancanın kendisi bozulursa TÜM Bash komutlarını kilitlememeli).
    sys.exit(0)

komut = veri.get("tool_input", {}).get("command", "") or ""

_TEHLIKELI_DESENLER = [
    r"git\s+add\s+.*(-f\b|--force\b).*\.env\b",
    r"git\s+add\s+.*\.env\b.*(-f\b|--force\b)",
]

for desen in _TEHLIKELI_DESENLER:
    if re.search(desen, komut):
        sys.stderr.write(
            ".env dosyasini gitignore'u FORCE ile bypass ederek git'e "
            "eklemeye calisiyorsun -- bu dosyada gercek sirlar var "
            "(Render API anahtari, admin sifresi, Sentry/B2 token'lari). "
            "Kasitliyse once kullaniciya acikca sor, sessizce ekleme."
        )
        sys.exit(2)

sys.exit(0)
