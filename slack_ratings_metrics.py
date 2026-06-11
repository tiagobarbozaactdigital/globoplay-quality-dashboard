#!/usr/bin/env python3
"""
Slack #globoplay-ratings — Métricas Estratégicas de Qualidade de Software.

Extrai métricas acionáveis para melhoria contínua do app Globoplay a partir
das reviews postadas pelo Appbot no canal Slack #globoplay-ratings.

Métricas produzidas:
  • NPS estimado (Net Promoter Score) global e por plataforma/versão
  • Categorização automática de problemas (crash, playback, performance, UI…)
  • Score de qualidade por versão do app
  • Ranking de dispositivos/versões de SO mais problemáticos
  • Detecção de sugestões de melhoria dos usuários
  • Tendência diária de satisfação
  • Top problemas por frequência e impacto

Uso:
    SLACK_TOKEN="xoxb-..." python3 slack_ratings_metrics.py --days 30 --outdir out
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_CHANNEL = "C02LAS2LS20"
PAGE_LIMIT = 200

# ========================== CATEGORIAS DE PROBLEMAS ==========================
# Cada categoria mapeia para uma lista de padrões regex.
# Isso permite gerar um "Top Problemas" estratégico para o time de QA.
PROBLEM_CATEGORIES: dict[str, list[str]] = {
    "Crash/Travamento": [
        r"crash(ou|ed|ando|es)?",
        r"trava(ndo|ou|r|mento)?",
        r"fecha\s*sozinho",
        r"for[çc]a\s*(o\s*)?fechamento",
        r"parou\s+de\s+funcionar",
        r"reinicia(ndo|ou|r)?",
        r"app\s+(fecha|fechou|fechando)",
    ],
    "Playback/Reprodução": [
        r"n[aã]o\s+(reproduz|carrega|roda|toca|funciona)",
        r"nem\s+carrega",
        r"tela\s+preta",
        r"sem\s+(imagem|v[ií]deo)",
        r"buffer(ing|izando)?",
        r"n[aã]o\s+reproduz(ir)?",
        r"pausa\s+sozinho",
        r"trava\s+no\s+(meio|in[ií]cio|come[çc]o)",
        r"n[aã]o\s+continua",
        r"n[aã]o\s+avan[çc]a",
        r"loading\s+(infinit|etern)",
        r"loading",
        r"n[aã]o\s+poss[ií]vel\s+reproduzir",
        r"conte[úu]do\s+indispon[ií]vel",
    ],
    "Áudio": [
        r"sem\s+([aá]udio|som)",
        r"[aá]udio\s+(sumiu|desaparec|cortando|falhando|atrasa)",
        r"som\s+(sumiu|cortando|falhando|n[aã]o\s+sai)",
        r"dessincroniza",
        r"audio\s+e\s+video\s+(dessincron|fora\s+de\s+sincroni)",
        r"legenda.*[aá]udio",
    ],
    "Performance/Lentidão": [
        r"lento",
        r"lentid[aã]o",
        r"demora(ndo)?\s+(para|pra|muito)",
        r"carrega(mento)?\s+lento",
        r"engasga(ndo)?",
        r"lag(ando)?",
        r"consumo\s+de\s+(bateria|mem[oó]ria|dados)",
        r"esquenta(ndo)?",
        r"aquece(ndo)?",
    ],
    "Login/Autenticação": [
        r"n[aã]o\s+(consigo\s+)?(logar|entrar|acessar|fazer\s+login)",
        r"login\s+(n[aã]o|falh|erro)",
        r"senha\s+(n[aã]o|errad|inv[aá]lid)",
        r"logout\s+sozinho",
        r"deslogou",
        r"sess[aã]o\s+(expir|encerr)",
    ],
    "Interface/UX": [
        r"interface",
        r"design",
        r"bot[aã]o\s+(n[aã]o|sum|desaparec)",
        r"dif[ií]cil\s+de\s+(usar|encontrar|navegar)",
        r"confuso",
        r"n[aã]o\s+(encontr|ach)\w*\s+(o|a|onde)",
        r"menu",
        r"layout",
        r"usabilidade",
        r"brilho",
        r"veloc[ií]metro",
        r"controle\s+de\s+(velocidade|som|brilho)",
    ],
    "Conectividade/Rede": [
        r"sem\s+(internet|conex[aã]o|rede|sinal)",
        r"erro\s+de\s+(conex[aã]o|rede)",
        r"timeout",
        r"fora\s+do\s+ar",
        r"indispon[ií]vel",
        r"servidor",
        r"n[aã]o\s+conecta",
    ],
    "Cast/Espelhamento": [
        r"chromecast",
        r"\bcast\b",
        r"espelha(mento|ndo|r)?",
        r"airplay",
        r"miracast",
    ],
    "Assinatura/Pagamento": [
        r"cobr(an[çc]a|ando|ou)",
        r"assinatura",
        r"cancelar",
        r"cancelamento",
        r"pagamento",
        r"n[aã]o\s+(reconhec|valid)\w*\s+assinatura",
        r"plano",
    ],
    "Conteúdo": [
        r"conte[uú]do\s+(sum|desaparec|falt|n[aã]o\s+tem)",
        r"epis[oó]dio\s+(sum|falt|n[aã]o\s+tem)",
        r"legenda\s+(errad|falt|n[aã]o|atrasa)",
        r"catálogo",
        r"s[eé]rie\s+(sum|falt|n[aã]o\s+tem)",
    ],
}

# Compila os padrões de cada categoria
_COMPILED_CATEGORIES: dict[str, re.Pattern] = {
    cat: re.compile("|".join(patterns), re.IGNORECASE)
    for cat, patterns in PROBLEM_CATEGORIES.items()
}

# Padrões para detectar SUGESTÕES de melhoria dos usuários
SUGGESTION_PATTERNS = re.compile(
    r"(poderia[m]?\s|deveria[m]?\s|seria\s+bom|sugiro|sugest[aã]o|"
    r"gostaria\s+que|falta(va|ndo)?\s|precisa(va)?\s+(de\s+)?|"
    r"colocar\s+(pelo\s+menos|ao\s+menos)|"
    r"melhorar|adicionar|incluir|implementar|liberar|disponibilizar|"
    r"por\s+favor\s+(coloque|adicione|melhore|libere|fa[çc]a))",
    re.IGNORECASE,
)

# Regex para extrair dados estruturados do Appbot
_RE_STARS = re.compile(r"([★☆]+)")
_RE_SENTIMENT = re.compile(r"(Positive|Negative|Neutral|Mixed)", re.I)
_RE_VERSION = re.compile(r"v(\d+\.\d+[\.\d]*)")
_RE_DEVICE = re.compile(
    r"(?:Android|iOS)\s+[\d.]+\s*·\s*(.+?)\s*·\s*(?:Google\s*Play|App\s*Store)",
    re.IGNORECASE,
)
_RE_OS_VERSION = re.compile(r"(Android|iOS)\s+([\d.]+)", re.I)
_RE_STORE = re.compile(r"(Google\s*Play|App\s*Store|Apple\s*Store)", re.I)

# Plataforma
PLATAFORMA_RULES: list[tuple[str, re.Pattern]] = [
    ("Chromecast", re.compile(r"chromecast|\bcast\b", re.I)),
    ("Apple TV", re.compile(r"apple\s*tv|appletv|tvos", re.I)),
    ("Fire TV", re.compile(r"fire\s*tv|firestick|fire\s*stick|amazon\s*fire", re.I)),
    ("Smart TV", re.compile(r"smart\s*tv|samsung\s*tv|lg\s*tv|tizen|webos|roku", re.I)),
    ("Android", re.compile(r"android", re.I)),
    ("iOS", re.compile(r"\bios\b|iphone|ipad", re.I)),
    ("Web", re.compile(r"\bweb\b|navegador|browser|chrome|firefox|safari|edge", re.I)),
]


# ---------------------------------------------------------------------------
# Fetch com paginação + backoff
# ---------------------------------------------------------------------------

def fetch_messages(
    client: WebClient,
    channel: str,
    oldest: float,
    latest: float,
) -> list[dict]:
    """Busca todas as mensagens do canal no intervalo [oldest, latest]."""
    messages: list[dict] = []
    cursor: str | None = None
    page = 0

    while True:
        page += 1
        kwargs: dict = dict(
            channel=channel,
            oldest=str(oldest),
            latest=str(latest),
            limit=PAGE_LIMIT,
            inclusive=True,
        )
        if cursor:
            kwargs["cursor"] = cursor

        for attempt in range(1, 6):
            try:
                resp = client.conversations_history(**kwargs)
                break
            except SlackApiError as exc:
                if exc.response.status_code == 429:
                    retry_after = int(exc.response.headers.get("Retry-After", attempt * 2))
                    log.warning("Rate-limited. Aguardando %ds (tentativa %d)…", retry_after, attempt)
                    time.sleep(retry_after)
                else:
                    raise
        else:
            log.error("Falha após 5 tentativas de paginação.")
            sys.exit(1)

        batch = resp.get("messages", [])
        messages.extend(batch)
        log.info("Página %d: %d msgs (total: %d)", page, len(batch), len(messages))

        meta = resp.get("response_metadata") or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    return messages


# ---------------------------------------------------------------------------
# Extração de conteúdo dos blocks do Appbot
# ---------------------------------------------------------------------------

def _extract_blocks_text(blocks: list[dict]) -> dict:
    """Extrai review_text, header_text e metadata_text dos blocks do Appbot."""
    review_text = ""
    header_text = ""
    metadata_parts: list[str] = []

    for block in blocks:
        btype = block.get("type", "")
        if btype == "section":
            txt = block.get("text", {}).get("text", "")
            if txt:
                review_text = txt
        elif btype == "context":
            elements = block.get("elements", [])
            for el in elements:
                if el.get("type") == "mrkdwn":
                    t = el.get("text", "")
                    if "view>" in t or "translate>" in t:
                        metadata_parts.append(t)
                    elif "appbot.co/apps" in t and "|" in t:
                        header_text = t
                    else:
                        metadata_parts.append(t)
                elif el.get("type") == "plain_text":
                    metadata_parts.append(el.get("text", ""))
        elif btype == "rich_text":
            for el in block.get("elements", []):
                for sub in el.get("elements", []):
                    if sub.get("type") == "text":
                        review_text = sub.get("text", "")

    return {
        "review_text": review_text.strip(),
        "header_text": header_text.strip(),
        "metadata_text": " ".join(metadata_parts).strip(),
    }


def _extract_stars(text: str) -> int:
    m = _RE_STARS.search(text)
    return m.group(1).count("★") if m else 0


def _extract_sentiment(text: str) -> str:
    m = _RE_SENTIMENT.search(text)
    return m.group(1).capitalize() if m else ""


def _extract_app_version(metadata: str) -> str:
    m = _RE_VERSION.search(metadata)
    return m.group(0) if m else ""


def _extract_device(metadata: str) -> str:
    m = _RE_DEVICE.search(metadata)
    return m.group(1).strip() if m else ""


def _extract_os_version(metadata: str) -> tuple[str, str]:
    m = _RE_OS_VERSION.search(metadata)
    if m:
        return m.group(1).capitalize(), m.group(2)
    return "", ""


def _extract_store(metadata: str) -> str:
    m = _RE_STORE.search(metadata)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Classificadores estratégicos
# ---------------------------------------------------------------------------

def classificar_problemas(text: str) -> list[str]:
    """Retorna lista de categorias de problema detectadas no texto."""
    if not text:
        return []
    return [cat for cat, pat in _COMPILED_CATEGORIES.items() if pat.search(text)]


def detectar_sugestao(text: str) -> bool:
    """Detecta se o review contém sugestão de melhoria."""
    return bool(SUGGESTION_PATTERNS.search(text)) if text else False


def calcular_nps_classe(stars: int) -> str:
    """Classifica a review para cálculo de NPS.
    Promotor: 4-5 ★ | Neutro: 3 ★ | Detrator: 1-2 ★
    """
    if stars >= 4:
        return "promotor"
    elif stars == 3:
        return "neutro"
    elif stars >= 1:
        return "detrator"
    return ""


def classificar_plataforma(header: str, metadata: str, review: str) -> str:
    combined = f"{header} {metadata}"
    if re.search(r"\bandroid\b", combined, re.I):
        return "Android"
    if re.search(r"\bios\b|iphone|ipad", combined, re.I):
        return "iOS"
    if re.search(r"apple\s*tv|tvos", combined, re.I):
        return "Apple TV"
    if re.search(r"fire\s*tv|firestick|amazon\s*fire", combined, re.I):
        return "Fire TV"
    if re.search(r"chromecast", combined, re.I):
        return "Chromecast"
    if re.search(r"smart\s*tv|samsung|lg\s*tv|tizen|webos|roku", combined, re.I):
        return "Smart TV"
    if re.search(r"\bweb\b|browser", combined, re.I):
        return "Web"
    for name, pat in PLATAFORMA_RULES:
        if pat.search(review):
            return name
    return "unknown"


# ---------------------------------------------------------------------------
# Construção do DataFrame
# ---------------------------------------------------------------------------

def build_dataframe(messages: list[dict]) -> pd.DataFrame:
    rows = []
    for m in messages:
        ts_float = float(m["ts"])
        dt_utc = datetime.fromtimestamp(ts_float, tz=timezone.utc)
        dt_local = dt_utc.astimezone()

        blocks = m.get("blocks", [])
        extracted = _extract_blocks_text(blocks)

        review_text = extracted["review_text"]
        raw_text = m.get("text", "") or ""
        full_text = review_text if review_text else raw_text

        plataforma = classificar_plataforma(
            extracted["header_text"],
            extracted["metadata_text"],
            full_text,
        )

        stars = _extract_stars(review_text)
        sentiment = _extract_sentiment(review_text)
        app_version = _extract_app_version(extracted["metadata_text"])
        device = _extract_device(extracted["metadata_text"])
        os_name, os_version = _extract_os_version(extracted["metadata_text"])
        store = _extract_store(extracted["metadata_text"])

        problemas = classificar_problemas(full_text)
        is_sugestao = detectar_sugestao(full_text)
        nps_classe = calcular_nps_classe(stars)

        rows.append({
            "ts": m["ts"],
            "datetime": dt_local,
            "user": m.get("user", m.get("bot_id", "unknown")),
            "text": full_text,
            "stars": stars,
            "sentiment": sentiment,
            "nps_classe": nps_classe,
            "app_version": app_version,
            "plataforma": plataforma,
            "device": device,
            "os_name": os_name,
            "os_version": os_version,
            "store": store,
            "categorias_problema": "; ".join(problemas) if problemas else "",
            "qtd_problemas": len(problemas),
            "is_sugestao": is_sugestao,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["hora"] = df["datetime"].dt.hour
    df["dia"] = df["datetime"].dt.date
    df["semana"] = df["datetime"].dt.isocalendar().week.astype(int)
    return df


# ---------------------------------------------------------------------------
# Cálculo de NPS
# ---------------------------------------------------------------------------

def calcular_nps(df: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    """Calcula NPS = %promotores - %detratores. Retorna DataFrame."""
    rated = df[df["nps_classe"] != ""].copy()
    if rated.empty:
        return pd.DataFrame()

    if group_col:
        groups = rated.groupby(group_col)
    else:
        rated["_all"] = "Global"
        groups = rated.groupby("_all")

    rows = []
    for name, g in groups:
        total = len(g)
        promotores = (g["nps_classe"] == "promotor").sum()
        neutros = (g["nps_classe"] == "neutro").sum()
        detratores = (g["nps_classe"] == "detrator").sum()
        nps = round((promotores / total - detratores / total) * 100, 1)
        nota_media = round(g["stars"].mean(), 2)
        rows.append({
            group_col or "grupo": name,
            "total_reviews": total,
            "promotores": int(promotores),
            "neutros": int(neutros),
            "detratores": int(detratores),
            "nps": nps,
            "nota_media": nota_media,
        })

    return pd.DataFrame(rows).sort_values("nps", ascending=True)


# ---------------------------------------------------------------------------
# Score de Qualidade por Versão do App
# ---------------------------------------------------------------------------

def quality_score_por_versao(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula um score de qualidade para cada versão do app.
    Score = nota_media * 20 - (% reviews com problema) - (% detratores * 0.5)
    Quanto maior, melhor a qualidade percebida.
    """
    versioned = df[df["app_version"] != ""].copy()
    if versioned.empty:
        return pd.DataFrame()

    rows = []
    for ver, g in versioned.groupby("app_version"):
        total = len(g)
        rated = g[g["stars"] > 0]
        nota_media = rated["stars"].mean() if len(rated) else 0
        pct_com_problema = (g["qtd_problemas"] > 0).sum() / total * 100
        pct_detratores = (g["nps_classe"] == "detrator").sum() / total * 100 if total else 0
        score = round(nota_media * 20 - pct_com_problema - pct_detratores * 0.5, 1)
        rows.append({
            "app_version": ver,
            "total_reviews": total,
            "nota_media": round(nota_media, 2),
            "pct_com_problema": round(pct_com_problema, 1),
            "pct_detratores": round(pct_detratores, 1),
            "quality_score": score,
        })

    return pd.DataFrame(rows).sort_values("app_version", ascending=False)


# ---------------------------------------------------------------------------
# Exportação de CSVs
# ---------------------------------------------------------------------------

def export_csvs(df: pd.DataFrame, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) Mensagens individuais (com todas as colunas estratégicas)
    csv_msgs = outdir / "globoplay_mensagens.csv"
    df.to_csv(csv_msgs, index=False, encoding="utf-8")
    log.info("CSV mensagens: %s (%d linhas)", csv_msgs, len(df))

    # 2) Resumo dia × plataforma (para Grafana)
    resumo = (
        df.groupby(["dia", "plataforma"])
        .agg(
            total_mensagens=("ts", "count"),
            nota_media=("stars", lambda x: round(x[x > 0].mean(), 2) if (x > 0).any() else 0),
            instabilidades=("qtd_problemas", lambda x: (x > 0).sum()),
            detratores=("nps_classe", lambda x: (x == "detrator").sum()),
            promotores=("nps_classe", lambda x: (x == "promotor").sum()),
            sugestoes=("is_sugestao", "sum"),
        )
        .reset_index()
        .sort_values(["dia", "total_mensagens"], ascending=[True, False])
    )
    csv_resumo = outdir / "globoplay_resumo_dia_plataforma.csv"
    resumo.to_csv(csv_resumo, index=False, encoding="utf-8")
    log.info("CSV resumo dia/plataforma: %s (%d linhas)", csv_resumo, len(resumo))

    # 2) NPS Global
    nps_global = calcular_nps(df)
    if not nps_global.empty:
        csv_nps = outdir / "nps_global.csv"
        nps_global.to_csv(csv_nps, index=False, encoding="utf-8")
        log.info("CSV NPS global: %s", csv_nps)

    # 3) NPS por Plataforma
    nps_plat = calcular_nps(df, "plataforma")
    if not nps_plat.empty:
        csv_nps_plat = outdir / "nps_por_plataforma.csv"
        nps_plat.to_csv(csv_nps_plat, index=False, encoding="utf-8")
        log.info("CSV NPS por plataforma: %s", csv_nps_plat)

    # 4) NPS por Versão do App
    nps_ver = calcular_nps(df, "app_version")
    if not nps_ver.empty:
        csv_nps_ver = outdir / "nps_por_versao.csv"
        nps_ver.to_csv(csv_nps_ver, index=False, encoding="utf-8")
        log.info("CSV NPS por versão: %s", csv_nps_ver)

    # 5) Quality Score por Versão
    qs = quality_score_por_versao(df)
    csv_qs = outdir / "quality_score_por_versao.csv"
    if not qs.empty:
        qs.to_csv(csv_qs, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=["app_version", "total_reviews", "nota_media", "pct_com_problema", "pct_detratores", "quality_score"]).to_csv(csv_qs, index=False, encoding="utf-8")
    log.info("CSV quality score: %s", csv_qs)

    # 6) Top Categorias de Problema
    problem_rows = df[df["categorias_problema"] != ""]
    if not problem_rows.empty:
        all_cats: list[str] = []
        for cats in problem_rows["categorias_problema"]:
            all_cats.extend([c.strip() for c in cats.split(";")])
        cat_counts = pd.DataFrame(
            Counter(all_cats).most_common(),
            columns=["categoria_problema", "ocorrencias"],
        )
        cat_counts["pct_do_total"] = (cat_counts["ocorrencias"] / len(df) * 100).round(1)
        csv_cats = outdir / "top_problemas.csv"
        cat_counts.to_csv(csv_cats, index=False, encoding="utf-8")
        log.info("CSV top problemas: %s", csv_cats)

    # 7) Problemas por Plataforma
    if not problem_rows.empty:
        plat_problem = []
        for _, row in problem_rows.iterrows():
            for cat in row["categorias_problema"].split("; "):
                plat_problem.append({"plataforma": row["plataforma"], "categoria": cat})
        plat_df = pd.DataFrame(plat_problem)
        plat_pivot = plat_df.groupby(["plataforma", "categoria"]).size().reset_index(name="ocorrencias")
        plat_pivot = plat_pivot.sort_values(["plataforma", "ocorrencias"], ascending=[True, False])
        csv_plat_prob = outdir / "problemas_por_plataforma.csv"
        plat_pivot.to_csv(csv_plat_prob, index=False, encoding="utf-8")
        log.info("CSV problemas por plataforma: %s", csv_plat_prob)

    # 8) Dispositivos mais problemáticos
    devices_df = df[(df["device"] != "") & (df["qtd_problemas"] > 0)]
    csv_dev = outdir / "dispositivos_problematicos.csv"
    if not devices_df.empty:
        dev_rank = (
            devices_df.groupby("device")
            .agg(
                reviews_com_problema=("ts", "count"),
                nota_media=("stars", lambda x: round(x[x > 0].mean(), 2) if (x > 0).any() else 0),
            )
            .reset_index()
            .sort_values("reviews_com_problema", ascending=False)
            .head(20)
        )
        dev_rank.to_csv(csv_dev, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=["device", "reviews_com_problema", "nota_media"]).to_csv(csv_dev, index=False, encoding="utf-8")
    log.info("CSV dispositivos problemáticos: %s", csv_dev)

    # 9) Sugestões de melhoria dos usuários
    sugestoes = df[df["is_sugestao"]].copy()
    if not sugestoes.empty:
        csv_sug = outdir / "sugestoes_usuarios.csv"
        sugestoes[["datetime", "plataforma", "stars", "text"]].to_csv(
            csv_sug, index=False, encoding="utf-8"
        )
        log.info("CSV sugestões: %s (%d)", csv_sug, len(sugestoes))

    # 10) Tendência diária de satisfação
    daily = (
        df[df["stars"] > 0]
        .groupby("dia")
        .agg(
            reviews=("ts", "count"),
            nota_media=("stars", "mean"),
            pct_negativo=("sentiment", lambda x: round((x == "Negative").sum() / len(x) * 100, 1)),
            problemas_reportados=("qtd_problemas", lambda x: (x > 0).sum()),
            sugestoes=("is_sugestao", "sum"),
        )
        .reset_index()
    )
    daily["nota_media"] = daily["nota_media"].round(2)
    csv_daily = outdir / "tendencia_diaria.csv"
    daily.to_csv(csv_daily, index=False, encoding="utf-8")
    log.info("CSV tendência diária: %s", csv_daily)

    # 11) Distribuição geral de sentimento
    sent_df = df[df["sentiment"] != ""]
    if not sent_df.empty:
        sent_dist = (
            sent_df.groupby("sentiment")
            .size()
            .reset_index(name="total")
            .sort_values("total", ascending=False)
        )
        sent_dist["percentual"] = (sent_dist["total"] / sent_dist["total"].sum() * 100).round(1)
        csv_sent = outdir / "sentimento_geral.csv"
        sent_dist.to_csv(csv_sent, index=False, encoding="utf-8")
        log.info("CSV sentimento geral: %s", csv_sent)
    else:
        pd.DataFrame(columns=["sentiment", "total", "percentual"]).to_csv(
            outdir / "sentimento_geral.csv", index=False, encoding="utf-8"
        )

    # 12) Sentimento por plataforma
    if not sent_df.empty:
        sent_plat = (
            sent_df.groupby(["plataforma", "sentiment"])
            .size()
            .reset_index(name="total")
            .sort_values(["plataforma", "total"], ascending=[True, False])
        )
        csv_sent_plat = outdir / "sentimento_por_plataforma.csv"
        sent_plat.to_csv(csv_sent_plat, index=False, encoding="utf-8")
        log.info("CSV sentimento por plataforma: %s", csv_sent_plat)
    else:
        pd.DataFrame(columns=["plataforma", "sentiment", "total"]).to_csv(
            outdir / "sentimento_por_plataforma.csv", index=False, encoding="utf-8"
        )

    # 13) Tendência diária de sentimento
    if not sent_df.empty:
        sent_daily = (
            sent_df.groupby(["dia", "sentiment"])
            .size()
            .reset_index(name="total")
            .pivot_table(index="dia", columns="sentiment", values="total", fill_value=0)
            .reset_index()
        )
        for col in ["Negative", "Positive", "Neutral", "Mixed"]:
            if col not in sent_daily.columns:
                sent_daily[col] = 0
        sent_daily = sent_daily[["dia", "Positive", "Neutral", "Negative"] +
                                 (["Mixed"] if "Mixed" in sent_df["sentiment"].values else [])]
        csv_sent_daily = outdir / "sentimento_diario.csv"
        sent_daily.to_csv(csv_sent_daily, index=False, encoding="utf-8")
        log.info("CSV sentimento diário: %s", csv_sent_daily)
    else:
        pd.DataFrame(columns=["dia", "Positive", "Neutral", "Negative"]).to_csv(
            outdir / "sentimento_diario.csv", index=False, encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Resumo estratégico no terminal
# ---------------------------------------------------------------------------

def print_strategic_summary(df: pd.DataFrame) -> None:
    total = len(df)
    rated = df[df["stars"] > 0]

    print("\n" + "=" * 70)
    print("  📊 RELATÓRIO ESTRATÉGICO DE QUALIDADE — GLOBOPLAY")
    print("=" * 70)

    # --- NPS ---
    if not rated.empty:
        promotores = (df["nps_classe"] == "promotor").sum()
        detratores = (df["nps_classe"] == "detrator").sum()
        nps = round((promotores / len(rated) - detratores / len(rated)) * 100, 1)
        nota_media = round(rated["stars"].mean(), 2)
        print(f"\n  ⭐ Nota média: {nota_media}  |  📈 NPS estimado: {nps}")
        print(f"     Promotores (4-5★): {promotores}  |  Detratores (1-2★): {detratores}  |  Total avaliadas: {len(rated)}")

    # --- Top Problemas ---
    problem_df = df[df["categorias_problema"] != ""]
    if not problem_df.empty:
        all_cats: list[str] = []
        for cats in problem_df["categorias_problema"]:
            all_cats.extend([c.strip() for c in cats.split(";")])
        top = Counter(all_cats).most_common(7)
        print(f"\n  🔴 TOP PROBLEMAS ({len(problem_df)} reviews com problema de {total} total):")
        for cat, cnt in top:
            pct = cnt / total * 100
            bar = "█" * int(pct / 2)
            print(f"     {cat:<25s} {cnt:>4d} ({pct:>5.1f}%) {bar}")

    # --- NPS por Plataforma ---
    nps_plat = calcular_nps(df, "plataforma")
    if not nps_plat.empty:
        print("\n  📱 NPS POR PLATAFORMA:")
        for _, row in nps_plat.iterrows():
            emoji = "🟢" if row["nps"] > 0 else "🔴"
            print(f"     {emoji} {row['plataforma']:<14s}  NPS: {row['nps']:>6.1f}  ⭐ {row['nota_media']:.2f}  ({row['total_reviews']} reviews)")

    # --- Quality Score por Versão (top 5 mais recentes) ---
    qs = quality_score_por_versao(df)
    if not qs.empty:
        print("\n  🏗️  QUALITY SCORE POR VERSÃO DO APP (top 5):")
        for _, row in qs.head(5).iterrows():
            emoji = "🟢" if row["quality_score"] > 50 else "🟡" if row["quality_score"] > 20 else "🔴"
            print(f"     {emoji} {row['app_version']:<12s}  Score: {row['quality_score']:>6.1f}  ⭐ {row['nota_media']:.2f}  Problemas: {row['pct_com_problema']:.0f}%  ({row['total_reviews']} reviews)")

    # --- Dispositivos mais problemáticos ---
    devices = df[(df["device"] != "") & (df["qtd_problemas"] > 0)]
    if not devices.empty:
        top_dev = devices.groupby("device").size().sort_values(ascending=False).head(5)
        print("\n  📱 DISPOSITIVOS MAIS PROBLEMÁTICOS:")
        for dev, cnt in top_dev.items():
            print(f"     {dev:<25s} {cnt:>4d} reviews com problema")

    # --- Sugestões ---
    sugestoes = df[df["is_sugestao"]]
    if not sugestoes.empty:
        print(f"\n  💡 SUGESTÕES DE MELHORIA: {len(sugestoes)} reviews contêm sugestões")
        for _, row in sugestoes.head(3).iterrows():
            texto_curto = row["text"][:120].replace("\n", " ")
            print(f"     • [{row['plataforma']}] \"{texto_curto}...\"")

    # --- Sentimento ---
    if "sentiment" in df.columns:
        sent = df[df["sentiment"] != ""].groupby("sentiment").size().sort_values(ascending=False)
        if not sent.empty:
            print("\n  🎭 SENTIMENTO:")
            for s, cnt in sent.items():
                pct = cnt / total * 100
                print(f"     {s:<14s} {cnt:>5d} ({pct:.1f}%)")

    print("\n" + "=" * 70)
    print(f"  Total de reviews analisadas: {total}")
    print(f"  Período: {df['dia'].min()} → {df['dia'].max()}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Métricas estratégicas de qualidade — canal #globoplay-ratings.",
    )
    p.add_argument("--channel", default=DEFAULT_CHANNEL, help="ID do canal Slack")
    p.add_argument("--days", type=int, default=30, help="Dias para análise (default: 30)")
    p.add_argument("--outdir", default="out", help="Diretório de saída (default: out)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    token = os.getenv("SLACK_TOKEN")
    if not token:
        log.error(
            "Variável SLACK_TOKEN não definida.\n"
            '  export SLACK_TOKEN="xoxb-SEU-TOKEN-AQUI"'
        )
        sys.exit(1)

    client = WebClient(token=token)

    now = datetime.now(tz=timezone.utc)
    oldest_dt = now - timedelta(days=args.days)
    log.info("Canal: %s | Período: %s → %s (%d dias)", args.channel, oldest_dt.date(), now.date(), args.days)

    messages = fetch_messages(client, args.channel, oldest_dt.timestamp(), now.timestamp())

    if not messages:
        log.info("Nenhuma mensagem no período.")
        sys.exit(0)

    log.info("Total bruto de mensagens: %d", len(messages))

    df = build_dataframe(messages)
    if df.empty:
        log.info("DataFrame vazio. Encerrando.")
        sys.exit(0)

    outdir = Path(args.outdir)
    export_csvs(df, outdir)
    print_strategic_summary(df)
    log.info("✅ Concluído. CSVs em: %s/", outdir)


if __name__ == "__main__":
    main()
