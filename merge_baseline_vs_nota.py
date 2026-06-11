import pandas as pd

df_nota = pd.read_csv("out/tendencia_diaria.csv")
df_baseline = pd.read_csv("out/baseline_timeseries.csv")

# garantir mesmo formato de data

df_nota["dia"] = pd.to_datetime(df_nota["dia"]).dt.tz_localize(None)
df_baseline["dia"] = pd.to_datetime(df_baseline["dia"]).dt.tz_localize(None)


# JOIN
df = df_nota.merge(df_baseline, on="dia", how="left")

# formato grafana
df["dia"] = df["dia"].dt.strftime("%Y-%m-%dT00:00:00Z")

# salvar
df[["dia", "nota_media", "baseline_14d"]].to_csv(
    "out/baseline_vs_nota.csv",
    index=False
)

print("✅ dataset combinado gerado")
