import numpy as np
import pandas as pd
import geopandas as gpd
from . import utils_func

@utils_func.timer
def get_datas():
    df = pd.read_csv("datas/interventions/inter_23_modifie.csv")
    df = df.dropna(
        subset=["traitement", "x", "y"]
    )  # On retire les interventions impossible à exploiter (possiblement générer de faux temps à l'avenir)
    df = pd.merge(
        df,
        pd.read_csv("datas/interventions/cma_inter.csv"),
        on="IdMMASelection",
    )
    df["next"] = "inter"
    df = df[
        df["traitement"] > 60
    ]  # Uniquement les interventions de plus de 60s
    return df    

def format_engins():
    pompes_speciales = pd.read_csv("datas/utils/liste_engins_fix.csv")
    pompes_speciales = (
        pd.get_dummies(
            pompes_speciales[
                pompes_speciales["Type_VHL"].isin(["FMOGP", "FA", "PSE"])
            ],
            columns=["Type_VHL"],
            dtype=int,
            prefix="",
            prefix_sep="",
        )[["cs", "FA", "FMOGP", "PSE"]]
        .groupby("cs")
        .sum()
    ).reset_index()
    df = pd.read_csv("datas/utils/liste_engins_fix.csv")
    df = df.groupby(["cs", "Interventions"]).sum().reset_index()
    df = df.sort_values(["cs", "Interventions"])
    df = df.pivot(index=["cs"], columns="Interventions", values="disponible")
    df = df.reset_index().sort_values("cs")
    df = df.sort_index()
    df = df.groupby("cs", sort=False).sum(numeric_only=True).reset_index()
    df = df.merge(pompes_speciales, on="cs", how="left").fillna(0)
    # Décompte des pompes spéciales
    df["POMPE"] = df["POMPE"] - df["FA"] - df["FMOGP"] - df["PSE"]
    df["VSAV"] = df["VSAV"] - df["PSE"]
    return df


def generation_liste(df: pd.DataFrame):
    # PSE étant 1 VSAV et 1 EP il faut le répercuter, je le soustrais précédemment par lisibilité au niveau de la carte
    df["VSAV"] = df["VSAV"] + df["PSE"]
    df_long = pd.melt(
        df[["cs", "VSAV", "PSE", "POMPE", "FA", "FMOGP"]],
        id_vars="cs",
        var_name="Interventions",
    )
    df_long = df_long.loc[
        df_long.index.repeat(df_long["value"])
    ]  # Duplique les lignes n° défini par champ value
    df_long["ordre"] = (
        df_long.groupby(["cs", "Interventions"]).cumcount() + 1
    )  # Ajout de "l'ordre"
    df_long = df_long.reset_index(drop=True)  # Index dupliqués
    df_long = df_long.reset_index(names="id")  # Ajout de l'index final
    df_long["id"] = df_long["id"] + 1
    liaison = df_long.merge(df[df["PSE"] == 1]["cs"], on="cs")
    liaison = liaison[
        (
            (liaison["Interventions"] == "VSAV")
            | (liaison["Interventions"] == "PSE")
        )
        & (liaison["value"] == liaison["ordre"])
    ]
    liaison["VSAV"] = liaison.groupby("cs")["id"].shift(1).fillna(0)
    liaison["PSE"] = liaison.groupby("cs")["id"].shift(-1).fillna(0)
    liaison["modularite"] = liaison["VSAV"] + liaison["PSE"]
    liaison = liaison.drop(columns=["PSE", "VSAV"]).reset_index(drop=True)
    df_long = df_long.merge(
        liaison[["id", "modularite"]], on="id", how="left"
    ).fillna(0)
    df_long["Regime"] = np.where(
        df_long["modularite"] != 0, "Modulaire", "Soclé"
    )
    df_long["Type_VHL"] = df_long["Interventions"]
    df_long['disponible'] = 1
    df_long['Interventions'] = df_long['Interventions'].replace({'FA': 'POMPE','PSE':'POMPE','FMOGP':'POMPE'})
    df_long['pse'] = (df_long['Type_VHL'] == 'PSE').astype(int)
    return pd.merge(
        df_long.drop(columns=["value"]), pd.read_csv("datas/utils/lso.csv"), on="cs"
    ).set_index("id")


def generate_gdf():
    df = pd.read_csv("datas/utils/liste_engins_finale.csv")
    gdf = gpd.read_file("datas/geo/secteurs_cs.geojson").to_crs(epsg=4326).dropna()
    gdf["compagnie"] = gdf["compagnie"].astype(int)
    return (
        gdf.merge(df, left_on="nom", right_on="cs", how="left")
        .drop(columns="cs")
        .fillna(0)
    ).rename(columns={"nom": "cs"})