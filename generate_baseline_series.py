import pandas as pd

## =========================
## CONFIG
## =========================

BASELINE_WINDOW_DAYS = 14

## =========================
## LOAD
## =========================

df = pd.read_csv("out/tendencia_diaria.csv")
df["dia"] = pd.to_datetime(df["dia"])

df = df.sort_values("dia")

## =========================
## BASELINE DIÁRIO (rolling)
## =========================

def calcular_baseline_rolling(df):
    baselines = []

    for i, row in df.iterrows():

        dia_atual = row["dia"]
        inicio_janela = dia_atual - pd.Timedelta(days=BASELINE_WINDOW_DAYS)

        janela = df[
            (df["dia"] < dia_atual) &
            (df["dia"] >= inicio_janela)
        ]

        baseline = janela["nota_media"].mean()

        baselines.append(baseline)

    return baselines


df["baseline_14d"] = calcular_baseline_rolling(df)

## =========================
## FORMATO GRAFANA
## =========================

df["dia"] = df["dia"].dt.strftime("%Y-%m-%dT00:00:00Z")

## =========================
## OUTPUT
## =========================

df[["dia", "baseline_14d"]].to_csv(
    "out/baseline_timeseries.csv",
    index=False
)

print("✅ Baseline timeseries gerado com sucesso!")