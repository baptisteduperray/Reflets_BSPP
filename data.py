import pandas as pd
import geopandas as gpd
from classes import Engin, Intervention, Secteur, PSE, POMPE, VSAV, PSE_Engin, POMPE_Engin, VSAV_Engin
from typing import List, Tuple

def get_raw_interventions() -> gpd.GeoDataFrame:
    df = pd.merge(
        pd.read_csv("datas/interventions/inter_23_modifie.csv"),
        pd.read_csv("datas/interventions/cma_inter.csv"),
        on="IdMMASelection"
    ).dropna()
    df = df[df["cstc"] != "STEC"]
    df = df.rename(columns={
        "inter": "inter_id",
        "selection": "date",
        "traitement": "traitement", # Durée sur place + temps de retour
        "x": "x",
        "y": "y",
        "fem_mma": "fem_mma",
        "cstc": "cstc", # Centre de secours territoriellement competent
        "depart": "depart",
        "trajet": "trajet",
        "cs": "cs",
        "proc": "proc",
        # Inutile
        "engagement": "_engagement",
        "IdMMASelection": "_IdMMASelection",
        "grpt": "_grpt",
        "IdInterventionSolution": "_IdInterventionSolution",
        "CodeClasseFamilleMateriel": "_CodeClasseFamilleMateriel",
        "n_red": "_n_red",
    })
    
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs="EPSG:4326")

    # Transforme les temps pour pandas
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M")
    df = df.sort_values("date", ascending=True).reset_index(drop=True)
    df['id'] = range(0, len(df))
    df["traitement"] = pd.to_timedelta(df["traitement"], unit="s")
    df["depart"] = pd.to_timedelta(df["depart"], unit="s")
    df["trajet"] = pd.to_timedelta(df["trajet"], unit="s")

    # Ajoute des catégories
    if "cs_secteur" in df.columns:
        df["cs_secteur"] = df["cs_secteur"].astype("category")
    if "proc" in df.columns:
        df["proc"] = df["proc"].astype("category")
    if "type" in df.columns:
        df["type"] = df["type"].astype("category")
    
    return df

def get_interventions() -> list[Intervention]:
    df = get_raw_interventions()
    Intervention.df = df

    interventions = []

    for inter in df.itertuples():
        interventions.append(Intervention(
            proc=getattr(inter, "proc"),
            id=getattr(inter, "id"),
            x=getattr(inter, "x"),
            y=getattr(inter, "y"),
            date=getattr(inter, "date").to_pydatetime(),
            traitement=getattr(inter, "traitement").to_pytimedelta(),
            trajet=getattr(inter, "trajet").to_pytimedelta(),
            fem_mma=getattr(inter, "fem_mma"),
            cstc=getattr(inter, "cstc")
        ))
    
    return interventions

def get_raw_secteurs() -> gpd.GeoDataFrame:
    df = gpd.read_file("datas/geo/secteurs_cs.geojson").dropna()
    df_utils = pd.read_csv("datas/utils/lso.csv")
    df = df.merge(df_utils, how="left", left_on="nom", right_on="cs")
    df.drop(columns=["cs"], inplace=True)
    df = df.rename(columns={
        "nom": "id",
        "geometry": "geometry",
        "x": "x",
        "y": "y",
        # Inutile
        "rg_cle": "_rg_cle",
        "node": "_node",
        "compagnie": "_compagnie",
    })

    # Donne l'emplacement du centre de secours
    if "x" in df.columns and "y" in df.columns:
        df["cs_geometry"] = gpd.points_from_xy(df["x"], df["y"])
        
    return df

def get_secteurs() -> dict[str, Secteur]:
    df = get_raw_secteurs()
    Secteur.df = df

    secteurs = {}

    for secteur in df.itertuples():
        secteurs[secteur.id] = Secteur(
            id=getattr(secteur, "id"),
            x=getattr(secteur, "x"),
            y=getattr(secteur, "y")
        )
    
    return secteurs

def get_raw_engins() -> gpd.GeoDataFrame:
    # Récupère les données et les regroupe
    df = pd.merge(
        pd.read_csv("datas/utils/liste_engins_fix.csv"),
        pd.read_csv("datas/utils/lso.csv"),
        on="cs"
    ).dropna()

    df["cs"] = df["id"].map(pd.read_csv("datas/utils/modifications_engins.csv").set_index("id")["cs"]).fillna(df["cs"])

    df = df.rename(columns={
        "id": "id",
        "Interventions": "intervention_fem_mma",
        "cs": "cs",
        "x": "x",
        "y": "y",
        "Type_VHL": "Type_VHL",
        "modularite": "modularite",
        # Inutile
        "Regime": "_Regime",
        "ordre": "_ordre",
        "id_cs": "_id_cs",
        "disponible": "_disponible",
        "node": "_node"
    })

    # GeoDataFrame with initial availability
    df = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["x"], df["y"]),
        crs="EPSG:4326"
    )

    # Met "id" en tant qu'index
    if "id" in df.columns and df["id"].is_unique:
        df = df.set_index("id", drop=False)

    # Ajoute des catégories
    if "cs" in df.columns:
        df["cs"] = df["cs"].astype("category")
    if "type_interventions" in df.columns:
        df["type_interventions"] = df["type_interventions"].astype("category")
    
    return df

def get_engins() -> dict[int, Engin]:
    df = get_raw_engins()
    Engin.df = df

    dict_engins = {}
    modularites: List[Tuple[Engin, int]] = [] # Il associe l engin a son modulaire
    
    for engin in df.itertuples():
        type_engin:  PSE_Engin | POMPE_Engin | VSAV_Engin | None = None
        if engin.Type_VHL == PSE:
            type_engin = PSE_Engin
        else:
            if engin.intervention_fem_mma == VSAV:
                type_engin = VSAV_Engin
            elif engin.intervention_fem_mma == POMPE:
                type_engin = POMPE_Engin

        dict_engins[engin.id] = type_engin(engin.id, engin.cs, engin.x, engin.y)
        modularites.append((dict_engins[engin.id], engin.modularite))

    for engin, engin_id in modularites:
        if engin_id != 0:
            engin.set_modularite(dict_engins[engin_id])
    
    return dict_engins

def get_data():
    interventions = get_interventions()
    secteurs = get_secteurs()
    engins = get_engins()
    return interventions, secteurs, engins
