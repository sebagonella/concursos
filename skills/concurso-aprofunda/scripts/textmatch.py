#!/usr/bin/env python3
"""
textmatch.py - Utilitários de normalização e similaridade textual.

Extraído do diff_editais.py da skill concurso-prep para ser reusado aqui na
localização de assuntos dentro do livro (casar nome do assunto mapeado com
títulos do sumário / trechos do texto). Sem dependências externas.
"""
import re
import unicodedata
from difflib import SequenceMatcher


# Stopwords PT curtas — removidas na indexação por termos, não na normalização geral.
STOPWORDS = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "em", "no", "na",
    "nos", "nas", "um", "uma", "por", "para", "com", "sem", "sob", "ao", "aos",
    "que", "se", "sua", "seu", "suas", "seus", "the", "of", "to",
}


def normalizar(texto: str) -> str:
    """Remove acentos, baixa caixa, tira pontuação. Base de todo o matching."""
    nfkd = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in nfkd if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def tokens_significativos(texto: str) -> list[str]:
    """Tokens normalizados com 3+ chars, sem stopwords. Para busca por densidade."""
    return [t for t in normalizar(texto).split() if len(t) >= 3 and t not in STOPWORDS]


def similaridade(a: str, b: str) -> float:
    """Razão de similaridade de sequência (0..1) entre dois textos já normalizados."""
    return SequenceMatcher(None, a, b).ratio()


def contencao_tokens(a: str, b: str) -> float:
    """Fração de tokens do menor conjunto contidos no maior (texto normalizado)."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    menor = ta if len(ta) <= len(tb) else tb
    return len(ta & tb) / len(menor)


def score_match(assunto: str, candidato: str) -> float:
    """Score combinado (0..1) de quão bem 'candidato' (ex: título de sumário)
    corresponde a 'assunto' (ex: tópico mapeado). Combina similaridade de
    sequência com contenção de tokens, favorecendo o maior sinal."""
    na, nc = normalizar(assunto), normalizar(candidato)
    if not na or not nc:
        return 0.0
    s = similaridade(na, nc)
    c = contencao_tokens(na, nc)
    # média ponderada, com a contenção ajudando quando um título é subconjunto do outro
    return round(max(s, 0.5 * s + 0.5 * c), 3)


def densidade_termos(texto_pagina: str, termos: list[str]) -> float:
    """Quantos dos 'termos' (já normalizados) aparecem na página, ponderado por
    frequência. Usado quando não há sumário: encontrar páginas mais relevantes
    a um assunto pela concentração de seus termos-chave."""
    if not termos:
        return 0.0
    norm = normalizar(texto_pagina)
    palavras = norm.split()
    if not palavras:
        return 0.0
    total = 0
    distintos = 0
    for termo in set(termos):
        c = palavras.count(termo)
        total += c
        if c > 0:
            distintos += 1
    # combina cobertura (quantos termos distintos aparecem) com frequência normalizada
    cobertura = distintos / len(set(termos))
    freq = total / len(palavras)
    return round(0.7 * cobertura + 0.3 * min(freq * 20, 1.0), 4)
