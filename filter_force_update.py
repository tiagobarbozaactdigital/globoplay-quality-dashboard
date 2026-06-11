#!/usr/bin/env python3
"""
Filtro histórico de reclamações sobre Force Update — Globoplay.

Lê o CSV processado (out/globoplay_mensagens.csv) e extrai todas as reviews
que mencionam atualização forçada / force update, gerando:
  • out/force_update_reviews.csv   — reviews individuais
  • out/force_update_por_dia.csv   — frequência diária
  • out/force_update_por_versao.csv — impacto por versão do app
  + resumo no terminal
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import Counter

import pandas as pd

# ---------------------------------------------------------------------------
# Padrões de Force Update
# ---------------------------------------------------------------------------
FORCE_UPDATE_PATTERN = re.compile(
    r"force.?update"
    r"|atualiz(a[çc][aã]o|ar|ando|ado|ou)"
    r"|update.?obrigat"
    r"|obriga(tório|da|ndo).*atualiz"
    r"|atualiz.*obrigat"
    r"|forçad.*atualiz"
    r"|pede.*atualiz"
    r"|pedindo.*atualiz"
    r"|solicita.*atualiz"
    r"|atualiz.*sess[aã]o"
    r"|nova.?vers[aã]o"
    r"|vers[aã]o.*desatualiz"
    r"|app.*desatualiz"
    r"|precisa.*atualiz"
    r"|atualize.*app"
    r"|update.*app",
    re.IGNORECASE,
)

# Sub-categorias para classificar o tipo de menção
SUBCATEGORIAS: list[tuple[str, re.Pattern]] = [
    ("Sessão expira / pede re-login", re.compile(
        r"atualiz.*sess[aã]o|sess[aã]o.*atualiz|solicita.*atualiz.*sess",
        re.I,
    )),
    ("Forçado a atualizar o app", re.compile(
        r"force.?update|obriga(tório|da|ndo).*atualiz|atualiz.*obrigat"
        r"|forçad.*atualiz|pede.*atualiz|pedindo.*atualiz|solicita.*atualiz"
        r"|atualize.*app|update.*app",
        re.I,
    )),
    ("Bugs pós-atualização", re.compile(
        r"(depois|ap[oó]s|desde).{0,30}atualiz|atualiz.{0,30}(bug|erro|falha|problema|piorou|parou|quebrou)",
        re.I,
    )),
    ("Nova versão com problemas", re.compile(
        r"nova.?vers[aã]o|vers[aã]o.*desatualiz|app.*desatualiz",
        re.I,
    )),
    ("Menção geral a atualização", re.compile(
        r"atualiz",
        re.I,
    )),
]


def classificar_subcategoria(text: str) -> str:
    """Retorna a subcategoria mais específica que match."""
    for nome, pat in SUBCATEGORIAS:
        if pat.search(text):
            return nome
    return "Outro"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    csv_path = Path("out/globoplay_mensagens.csv")
    if not csv_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {csv_path}")
        print("  Execute primeiro: SLACK_TOKEN=... python3 slack_ratings_metrics.py --days 90 --outdir out")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df["text"] = df["text"].astype(str).fillna("")

    # Filtra reviews com menção a force update / atualização
    mask = df["text"].str.contains(FORCE_UPDATE_PATTERN, na=False, regex=True)
    fu = df[mask].copy()

    if fu.empty:
        print("Nenhuma review sobre force update encontrada.")
        sys.exit(0)

    # Subcategoria
    fu["subcategoria"] = fu["text"].apply(classificar_subcategoria)

    # Garante coluna dia como string
    fu["dia"] = pd.to_datetime(fu["dia"]).dt.date if "dia" in fu.columns else fu["datetime"].str[:10]

    # Limpa texto para exibição
    def limpar(t: str) -> str:
        t = re.sub(r":[a-z_]+:", "", t)       # remove emoji codes do Slack
        t = re.sub(r"[★☆·]", "", t)           # remove estrelas
        t = re.sub(r"<[^>]+>", "", t)          # remove links
        t = re.sub(r"\s+", " ", t).strip()
        return t

    fu["texto_limpo"] = fu["text"].apply(limpar)

    # ---------------------------------------------------------------------------
    # Exportar CSVs
    # ---------------------------------------------------------------------------
    out = Path("out")
    out.mkdir(exist_ok=True)

    # 1) Reviews individuais
    cols = ["dia", "datetime", "plataforma", "app_version", "stars",
            "sentiment", "nps_classe", "subcategoria", "texto_limpo"]
    cols_existentes = [c for c in cols if c in fu.columns]
    csv_reviews = out / "force_update_reviews.csv"
    fu[cols_existentes].sort_values("dia").to_csv(csv_reviews, index=False, encoding="utf-8")
    print(f"✅ {csv_reviews}  ({len(fu)} reviews)")

    # 2) Frequência diária
    daily = (
        fu.groupby("dia")
        .agg(
            total=("texto_limpo", "count"),
            nota_media=("stars", lambda x: round(pd.to_numeric(x, errors="coerce").dropna().mean(), 2)),
            detratores=("nps_classe", lambda x: (x == "detrator").sum()),
            promotores=("nps_classe", lambda x: (x == "promotor").sum()),
        )
        .reset_index()
        .sort_values("dia")
    )
    csv_daily = out / "force_update_por_dia.csv"
    daily.to_csv(csv_daily, index=False, encoding="utf-8")
    print(f"✅ {csv_daily}  ({len(daily)} dias)")

    # 3) Impacto por versão do app
    if "app_version" in fu.columns:
        por_versao = (
            fu[fu["app_version"].fillna("") != ""]
            .groupby("app_version")
            .agg(
                total=("texto_limpo", "count"),
                nota_media=("stars", lambda x: round(pd.to_numeric(x, errors="coerce").dropna().mean(), 2)),
                detratores=("nps_classe", lambda x: (x == "detrator").sum()),
            )
            .reset_index()
            .sort_values("total", ascending=False)
        )
        csv_versao = out / "force_update_por_versao.csv"
        por_versao.to_csv(csv_versao, index=False, encoding="utf-8")
        print(f"✅ {csv_versao}  ({len(por_versao)} versões)")

    # 4) Por subcategoria
    por_sub = (
        fu.groupby("subcategoria")
        .agg(
            total=("texto_limpo", "count"),
            nota_media=("stars", lambda x: round(pd.to_numeric(x, errors="coerce").dropna().mean(), 2)),
            detratores=("nps_classe", lambda x: (x == "detrator").sum()),
        )
        .reset_index()
        .sort_values("total", ascending=False)
    )
    csv_sub = out / "force_update_por_subcategoria.csv"
    por_sub.to_csv(csv_sub, index=False, encoding="utf-8")
    print(f"✅ {csv_sub}  ({len(por_sub)} subcategorias)")

    # 5) Por plataforma
    if "plataforma" in fu.columns:
        por_plat = (
            fu.groupby("plataforma")
            .agg(
                total=("texto_limpo", "count"),
                nota_media=("stars", lambda x: round(pd.to_numeric(x, errors="coerce").dropna().mean(), 2)),
                detratores=("nps_classe", lambda x: (x == "detrator").sum()),
            )
            .reset_index()
            .sort_values("total", ascending=False)
        )
        csv_plat = out / "force_update_por_plataforma.csv"
        por_plat.to_csv(csv_plat, index=False, encoding="utf-8")
        print(f"✅ {csv_plat}  ({len(por_plat)} plataformas)")

    # ---------------------------------------------------------------------------
    # Resumo no terminal
    # ---------------------------------------------------------------------------
    total = len(fu)
    total_geral = len(df)

    print("\n" + "=" * 65)
    print("  🔄 RECLAMAÇÕES SOBRE FORCE UPDATE / ATUALIZAÇÃO — GLOBOPLAY")
    print("=" * 65)

    stars_num = pd.to_numeric(fu["stars"], errors="coerce")
    nota_media = round(stars_num.mean(), 2) if not stars_num.isna().all() else 0
    pct = total / total_geral * 100

    print(f"\n  Total de reviews: {total} de {total_geral} ({pct:.1f}% do total)")
    print(f"  Nota média nessas reviews: {nota_media} ⭐")

    if "nps_classe" in fu.columns:
        det = (fu["nps_classe"] == "detrator").sum()
        pro = (fu["nps_classe"] == "promotor").sum()
        print(f"  Detratores: {det}  |  Promotores: {pro}")

    # Subcategorias
    print("\n  📋 SUBCATEGORIAS:")
    for sub, cnt in Counter(fu["subcategoria"]).most_common():
        print(f"     {sub:<40s} {cnt:>4d}")

    # Por plataforma
    if "plataforma" in fu.columns:
        print("\n  📱 POR PLATAFORMA:")
        for plat, cnt in fu["plataforma"].value_counts().items():
            print(f"     {plat:<20s} {cnt:>4d}")

    # Por versão (top 5)
    if "app_version" in fu.columns:
        top_ver = fu[fu["app_version"].fillna("") != ""]["app_version"].value_counts().head(5)
        if not top_ver.empty:
            print("\n  🏷️  VERSÕES MAIS AFETADAS (top 5):")
            for ver, cnt in top_ver.items():
                print(f"     {ver:<20s} {cnt:>4d}")

    # Período
    dias = sorted(fu["dia"].unique())
    print(f"\n  📅 Período: {dias[0]} → {dias[-1]}  ({len(dias)} dias com ocorrências)")

    # Amostra de reviews
    print("\n  💬 AMOSTRA DE REVIEWS (10 mais recentes):")
    amostra = fu.sort_values("dia", ascending=False).head(10)
    for _, row in amostra.iterrows():
        stars_val = int(pd.to_numeric(row.get("stars", 0), errors="coerce") or 0)
        plat = row.get("plataforma", "?")
        ver = row.get("app_version", "")
        sub = row.get("subcategoria", "")
        texto = row["texto_limpo"][:140]
        print(f"\n     [{row['dia']}] {'★' * stars_val}{'☆' * (5 - stars_val)}  {plat}  {ver}")
        print(f"     [{sub}]")
        print(f"     \"{texto}\"")

    print("\n" + "=" * 65 + "\n")


if __name__ == "__main__":
    main()
