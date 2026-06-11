import pandas as pd

## =========================
## CONFIG
## =========================

BASELINE_WINDOW_DAYS = 14   # janela global (ex: últimos 14 dias)
LOCAL_BASELINE_DAYS = 3     # dias antes do evento (baseline dinâmico)

## =========================
## CARREGAR DADOS
## =========================

df_geral = pd.read_csv("out/tendencia_diaria.csv")
df_force = pd.read_csv("out/force_update_por_dia.csv")

## =========================
## PADRONIZAR DATAS
## =========================

df_geral["dia"] = pd.to_datetime(df_geral["dia"])
df_force["dia"] = pd.to_datetime(df_force["dia"])

## =========================
## RANGE COMPLETO
## =========================

date_range = pd.date_range(
    start=df_geral["dia"].min(),
    end=df_geral["dia"].max(),
    freq="D"
)

df_base = pd.DataFrame({"dia": date_range})

## =========================
## JOIN
## =========================

df = df_base.merge(df_geral, on="dia", how="left")
df = df.merge(df_force, on="dia", how="left")

## =========================
## TRATAMENTO
## =========================

df["total"] = df["total"].fillna(0)
df["reviews"] = df["reviews"].fillna(0)

df.rename(columns={
    "nota_media_x": "nota_media_geral",
    "nota_media_y": "nota_media_force"
}, inplace=True)

df["nota_media_force"] = df["nota_media_force"].fillna(df["nota_media_geral"])

df["pct_force_update"] = df["total"] / df["reviews"]
df["pct_force_update"] = df["pct_force_update"].fillna(0)

## =========================
## ✅ BASELINE GLOBAL (janela)
## =========================

max_date = df["dia"].max()
cutoff_date = max_date - pd.Timedelta(days=BASELINE_WINDOW_DAYS)

df_baseline = df[
    (df["pct_force_update"] == 0) &
    (df["dia"] >= cutoff_date)
]

baseline_global = df_baseline["nota_media_geral"].mean()

## =========================
## ✅ LAGS
## =========================

df["nota_d1"] = df["nota_media_geral"].shift(-1)
df["nota_d2"] = df["nota_media_geral"].shift(-2)

## =========================
## ✅ EVENTOS
## =========================

df_eventos = df[df["total"] > 0].copy()

## =========================
## ✅ BASELINE DINÂMICO (pré-evento)
## =========================

def calcular_baseline_local(row, df):
    dia_evento = row["dia"]
    inicio_janela = dia_evento - pd.Timedelta(days=LOCAL_BASELINE_DAYS)

    df_local = df[
        (df["dia"] < dia_evento) &
        (df["dia"] >= inicio_janela)
    ]

    return df_local["nota_media_geral"].mean()

df_eventos["baseline_local"] = df_eventos.apply(
    lambda row: calcular_baseline_local(row, df),
    axis=1
)

## =========================
## ✅ IMPACTOS
## =========================

# --- usando baseline global
impacto_direto_global = df_eventos["nota_media_geral"].mean() - baseline_global
impacto_d1_global = df_eventos["nota_d1"].mean() - baseline_global
impacto_d2_global = df_eventos["nota_d2"].mean() - baseline_global

# --- usando baseline local (mais preciso)
impacto_direto_local = (df_eventos["nota_media_geral"] - df_eventos["baseline_local"]).mean()
impacto_d1_local = (df_eventos["nota_d1"] - df_eventos["baseline_local"]).mean()
impacto_d2_local = (df_eventos["nota_d2"] - df_eventos["baseline_local"]).mean()

## =========================
## ✅ CORRELAÇÃO
## =========================

correlacao = df["pct_force_update"].corr(df["nota_media_geral"])

## =========================
## ✅ PRINTS
## =========================

print("\n📊 ===== ANÁLISE =====")

print(f"📌 Baseline global ({BASELINE_WINDOW_DAYS} dias): {baseline_global:.2f}")

print("\n--- Impacto (baseline GLOBAL) ---")
print(f"📉 Direto: {impacto_direto_global:.2f}")
print(f"📉 D+1: {impacto_d1_global:.2f}")
print(f"📉 D+2: {impacto_d2_global:.2f}")

print("\n--- Impacto (baseline LOCAL - mais confiável) ---")
print(f"📉 Direto: {impacto_direto_local:.2f}")
print(f"📉 D+1: {impacto_d1_local:.2f}")
print(f"📉 D+2: {impacto_d2_local:.2f}")

print(f"\n📊 Correlação: {correlacao:.2f}")

## =========================
## FORMATO GRAFANA
## =========================

df["dia"] = df["dia"].dt.strftime("%Y-%m-%dT00:00:00Z")

## =========================
## OUTPUT
## =========================

df.to_csv("out/force_update_vs_nota_media_v2.csv", index=False)

print("\n✅ Dataset + análise v2 gerados com sucesso!")