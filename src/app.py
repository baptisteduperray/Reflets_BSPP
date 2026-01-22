import marimo

__generated_with = "0.15.2"
app = marimo.App(width="full")

with app.setup:
    import warnings
    warnings.simplefilter(action='ignore', category=FutureWarning)
    import importlib
    import marimo as mo
    import plotly.express as px
    import geopandas as gpd
    import pandas as pd
    import numpy as np
    from datetime import timedelta
    from scipy.spatial import cKDTree
    import networkx as nx
    from carte_interactive import (
        draw_map,
        number_map,
        switch_map,
        update_gdf,
        generate_gdf,
        modif_df,
        infos,
    )
    import utils.simulation as si
    import utils.data_utils as du
    import utils.graph_utils as gu


@app.cell
def _():
    mo.md(
        f"""<div style="text-align: center;">
                            <h1>Partie paramétrage</h1>
                            </div>""",
    )
    return


@app.cell
def load_datas():
    gdf = du.generate_gdf().copy().reset_index()
    return (gdf,)


@app.cell
def buttons():
    button_update = mo.ui.refresh(
        label="Mettre à jour la carte", options=["5s", "15s", "1m", "10m"]
    )
    button_update_cs = mo.ui.run_button(label="Mettre à jour l'armement")
    button_run_sim = mo.ui.run_button(label="Simulation")
    return button_run_sim, button_update, button_update_cs


@app.cell
def refresh_map(button_update, gdf):
    carte = draw_map("VSAV", gdf)
    if button_update.value:
        print("rerunned")
    return (carte,)


@app.cell
def ui_elements(carte):
    number_vsav = number_map("VSAV", "VSAV", carte)
    number_ep = number_map("EP", "EP", carte)
    switch_ps = number_map("PSE", "PSE", carte)
    switch_fa = number_map("FA", "FA", carte)
    switch_fmo = number_map("FMOGP", "FMOGP", carte)
    return number_ep, number_vsav, switch_fa, switch_fmo, switch_ps


@app.cell
def _(button_update, carte):
    mo.vstack([button_update, mo.hstack([carte, mo.md("")])], align="center")
    return


@app.cell
def _(
    button_update_cs,
    carte,
    gdf,
    number_ep,
    number_vsav,
    switch_fa,
    switch_fmo,
    switch_ps,
):
    mo.stop(
        not carte.value,
        mo.md(
            f"""<div style="text-align: center;">
                            <h2>Cliquez sur un CS.</h2>
                            </div>""",
        ),
    )
    modif_df(
        gdf.iloc[carte.value[0]["i"]],
        number_vsav,
        number_ep,
        [switch_ps, switch_fa, switch_fmo],
        [button_update_cs],
    )
    return


@app.cell
def _(
    button_update_cs,
    carte,
    gdf,
    number_ep,
    number_vsav,
    switch_fa,
    switch_fmo,
    switch_ps,
):
    mo.stop(not button_update_cs.value)
    update_gdf(
        gdf,
        carte.value[0],
        vsav=number_vsav.value,
        ep=number_ep.value,
        ps=int(switch_ps.value),
        fa=int(switch_fa.value),
        fmo=int(switch_fmo.value),
    )
    infos(
        carte,
        vsav=number_vsav.value,
        ep=number_ep.value,
        ps=int(switch_ps.value),
        fa=int(switch_fa.value),
        fmo=int(switch_fmo.value),
    )
    return


@app.cell
def _():
    red_df = pd.read_csv("datas/interventions/red.csv")
    red = mo.ui.table(red_df, selection="single")
    return (red_df,)


@app.cell
def _(red_df):
    update_red = mo.ui.data_editor(
        pd.pivot_table(
            red_df[red_df["Engins"].isin(["EP", "VSAV", "FA", "FMOGP"])],
            values="Volume",
            index=[
                "CMA",
                "LibelleMotifAlerte",
                "IdInterventionSolution",
                "LibelleCompo",
            ],
            columns=["Engins"],
            aggfunc="sum",
        )
        .reset_index()
        .fillna(0)
    )
    return (update_red,)


@app.cell
def _(update_red):
    mo.accordion({"RED": update_red})
    return


@app.cell
def _():
    # TODO paramétrage RED: retirer nième engin du genre ou ajouter un faux départ du type d'engin
    pass
    return


@app.cell
def _():
    mo.md(
        f"""<div style="text-align: center;">
                            <h1>Partie simulation</h1>
                            </div>""",
    )
    return


@app.cell
def _():
    date_range = mo.ui.date_range(
        start="2023-01-01",
        stop="2023-12-31",
        value=["2023-01-01", "2023-01-02"],
    )
    mo.vstack(
        [
            mo.md(
                f"""<div style="text-align: center;">
                            <h2>Sélectionnez une plage de dates</h2>
                            </div>"""
            ),
            date_range,
        ],
        align="center",
    )
    return (date_range,)


@app.cell
def _():
    df = du.get_datas()
    return (df,)


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


@app.cell
def _():
    G = gu.load_network()
    return (G,)


@app.cell
def _(G, df_test, gdf):
    importlib.reload(si)
    engins = du.generation_liste(gdf.drop(columns=["index", "rg_cle", "geometry"]))
    sim = si.Simulation(df_test, engins.copy(), G)
    return (sim,)


@app.cell
def _(END, START, button_run_sim, sim):
    mo.stop(
        not button_run_sim.value,
        mo.vstack(
            [
                mo.md(
                    f"""<div style="text-align: center;">
                            <h2>Lancer la simulation</h2>
                            </div>"""
                ),
                button_run_sim,
            ],
            align="center",
        ),
    )

    en_cours_class, stats_engins_class = sim.run(START, END)

    mo.output.append(
        mo.md(
            f"""<div style="text-align: center;">
                            <h3>Simulation terminée</h3>
                            </div>"""
        ).callout(kind="info"),
    )
    return


@app.cell
def _(sim):
    sim.engins_courants.loc[[2]]
    return


@app.cell
def _(sim):
    sim.engins_courants.loc[(sim.en_cours[~(sim.en_cours['selection'] > '2023-05-15 00:00:00')]) & (sim.engins_courants['disponible'] == 0)]
    return


@app.cell
def _(sim):
    sim.engins_courants
    return


@app.cell
def _(sim):
    merged = pd.merge(sim.en_cours,sim.engins_courants,left_on='engin',right_index=True).sort_values('selection',ascending=False)
    return


if __name__ == "__main__":
    app.run()
