import marimo

__generated_with = "0.15.2"
app = marimo.App(width="full")

with app.setup:
    # cell: imports
    import importlib
    import marimo as mo
    import numpy as np
    import pandas as pd
    from datetime import timedelta
    from scipy.spatial import cKDTree
    import networkx as nx
    import time
    import utils.simulation as si
    from utils.data_utils import get_datas
    from utils.graph_utils import load_network

    importlib.reload(si)


@app.function(hide_code=True)
def cova():
    # Logique évoluant entre les GIS, les chefs et les dates
    # Impossible de vraiment programmer une algorithme pour suivre le raisonnement des BOIs
    # En cours : Récupération des indisponibilitées par engins et CS (approche de la COVA ainsi que d'autres variables, blessures, engins endommagés, etc...)
    pass


@app.cell
def _():
    G = load_network()
    return (G,)


@app.cell
def _():
    df = get_datas()
    return (df,)


@app.cell
def _():
    date_range = mo.ui.date_range(
        start="2023-01-01",
        stop="2023-12-31",
        value=["2023-01-01", "2023-01-02"],
        label="Choisir une plage de dates",
    )
    date_range
    return (date_range,)


@app.cell
def _(date_range, df):
    START = date_range.value[0].strftime("%Y-%m-%d")
    END = date_range.value[1].strftime("%Y-%m-%d")

    # Récréation de la df contenant que les dates à analyser
    df_test = df[(df["selection"] > START) & (df["selection"] < END)].copy()
    df_test["selection"] = pd.to_datetime(df_test["selection"])
    # Ajout d'un champ pour gérer la modularités lors de la concaténation des dataframes
    df_test["modularite"] = 0
    return END, START, df_test


@app.cell(hide_code=True)
def _():
    engins = pd.read_csv("datas/utils/liste_engins_fix.csv")
    engins["pse"] = (engins["Type_VHL"] == "PSE").astype(int)
    # Appliquer le filtre
    data_editor_engins = mo.ui.data_editor(engins).form(
        bordered=True,
        show_clear_button=True,
        submit_button_label="Valider",
        clear_button_label="Retirer modifications",
    )
    engins = 0
    data_editor_engins
    return (data_editor_engins,)


@app.cell(hide_code=True)
def _():
    button_run_sim = mo.ui.run_button(label="Lancer une simulation")
    button_rung_object = mo.ui.run_button(label="Lancer une simulation")
    return (button_run_sim,)


@app.cell
def _(END, G, START, button_run_sim, data_editor_engins, df_test):
    mo.stop(not button_run_sim.value, button_run_sim)
    engins_courants_c = pd.merge(
        data_editor_engins.value, pd.read_csv("datas/utils/lso.csv"), on="cs"
    ).set_index("id")
    sim = si.Simulation(df_test, engins_courants_c, G)
    en_cours_class, stats_engins_class = sim.run(START, END)
    return engins_courants_c, stats_engins_class


@app.cell
def _(engins_courants_c):
    engins_courants_c
    return


@app.cell
def _(stats_engins_class):
    stats_engins_class
    return


@app.cell
def _(END, G, START, button_run_sim, data_editor_engins, df_test, run):
    mo.stop(
        data_editor_engins.value is None, "Veuillez valider la table des engins"
    )
    mo.stop(not button_run_sim.value, button_run_sim)

    en_cours, stats_engins = run(
        START, END, df_test, data_editor_engins.value.set_index("id"), G, "1D"
    )
    return


if __name__ == "__main__":
    app.run()
