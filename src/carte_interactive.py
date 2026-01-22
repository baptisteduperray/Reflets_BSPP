import marimo

__generated_with = "0.15.2"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import plotly.express as px
    import geopandas as gpd
    import pandas as pd
    from utils.data_utils import generate_gdf, generation_liste


@app.cell
def _():
    filtered_gdf = generate_gdf().copy().reset_index()
    return (filtered_gdf,)


@app.cell
def buttons():
    button_update = mo.ui.refresh(
        label="Mettre à jour la carte", options=["5s", "15s", "1m", "10m"]
    )
    button_update_cs = mo.ui.run_button(label="Mettre à jour l'armement")
    return button_update, button_update_cs


@app.function
def draw_map(couleur: str, gdf: gpd.GeoDataFrame):
    fig = px.choropleth_map(
        gdf,
        geojson=gdf.geometry,
        locations=gdf["index"],
        color=couleur,
        hover_name="cs",
        map_style="open-street-map",
        center={"lat": 48.85, "lon": 2.35},
        zoom=9,
        color_continuous_scale="Speed",
        opacity=0.9,
    )
    fig.update_traces(
        customdata=gdf[["index", "cs", "VSAV", "POMPE", "PSE", "FA", "FMOGP"]],
        hovertemplate="<b>i=%{customdata[0]}<br>cs=%{customdata[1]}</b><br>VSAV=%{customdata[2]}<br>EP=%{customdata[3]},<br>PSE=%{customdata[4]},<br>FA=%{customdata[5]},<br>FMOGP=%{customdata[6]}",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        dragmode="pan",
        clickmode="event+select",
    )
    return mo.ui.plotly(
        fig,
        config={
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
            "displaylogo": False,
        },
    )


@app.cell
def _(button_update, filtered_gdf):
    carte = draw_map("VSAV", filtered_gdf)
    if button_update.value:
        print("rerunned")
    return (carte,)


@app.function
def switch_map(label: str, key: str, carte: mo.ui.plotly):
    if carte.value:
        datas = carte.value[0]
        return mo.ui.switch(label=label, value=bool(datas[key]))


@app.function
def number_map(label: str, key: str, carte: mo.ui.plotly):
    if carte.value:
        datas = carte.value[0]
        return mo.ui.number(start=0, stop=20, value=datas[key], label=label)


@app.cell
def _(carte):
    number_vsav = number_map("VSAV", "VSAV", carte)
    number_ep = number_map("EP", "EP", carte)
    switch_ps = switch_map("PSE", "PSE", carte)
    switch_fa = switch_map("FA", "FA", carte)
    switch_fmo = switch_map("FMOGP", "FMOGP", carte)
    return number_ep, number_vsav, switch_fa, switch_fmo, switch_ps


@app.function
def modif_df(
    datas,
    number_vsav: mo.ui.number,
    number_ep: mo.ui.number,
    switch: list[mo.ui.switch],
    button: list[mo.ui.run_button],
):
    couleur_vsav = (
        "red"
        if number_vsav.value > datas["VSAV"]
        else "green"
        if number_vsav.value < datas["VSAV"]
        else "cyan"
    )
    couleur_ep = (
        "red"
        if number_ep.value > datas["POMPE"]
        else "green"
        if number_ep.value < datas["POMPE"]
        else "cyan"
    )
    return mo.vstack(
        [
            mo.md(
                f"""<div style="text-align: center;">
                      <b><h2>{datas["cs"]}</h2></b>
                    </div>""",
            ),
            mo.hstack(
                [
                    number_vsav,
                    mo.md(
                        f"<span style='color:{couleur_vsav}'>/ {datas['VSAV']}</span>."
                    ),
                    number_ep,
                    mo.md(
                        f"<span style='color:{couleur_ep}'>/ {datas['POMPE']}</span>."
                    ),
                ],
                justify="center",
                align="center",
            ),
            mo.hstack(switch, justify="center"),
            mo.hstack(button, justify="center"),
        ]
    )


@app.cell
def _(carte):
    def interface():
        return carte
    return (interface,)


@app.function
def update_gdf(gdf: gpd.GeoDataFrame, datas: dict, **kwargs):
    # Utilisation de kwarggs pour facilté de lecture
    gdf.loc[datas["i"], "VSAV"] = kwargs.get("vsav", datas["VSAV"])
    gdf.loc[datas["i"], "POMPE"] = kwargs.get("ep", datas["EP"])
    gdf.loc[datas["i"], "PSE"] = kwargs.get("pse", datas["PSE"])
    gdf.loc[datas["i"], "FA"] = kwargs.get("fa", datas["FA"])
    gdf.loc[datas["i"], "FMOGP"] = kwargs.get("fmo", datas["FMOGP"])


@app.function
def infos(carte: mo.ui.plotly, **kwargs):
    datas = carte.value[0]
    return mo.vstack(
        [
            mo.md(f"##{datas['cs']} a bien été mis à jour :\n"),
            pd.DataFrame(
                {
                    "VSAV": [
                        datas["VSAV"],
                        kwargs.get("vsav", datas["VSAV"]),
                    ],
                    "EP": [datas["EP"], kwargs.get("ep", datas["EP"])],
                    "PSE": [datas["PSE"], kwargs.get("pse", datas["PSE"])],
                    "FA": [datas["FA"], kwargs.get("fa", datas["FA"])],
                    "FMOGP": [
                        datas["FMOGP"],
                        kwargs.get("fmo", datas["FMOGP"]),
                    ],
                },
                index=["Ancien armement", "Nouvel armement"],
            ),
        ],
        align="center",
    )


@app.cell
def _(button_update, interface):
    mo.vstack(
        [
            button_update,
            mo.hstack([interface()]),
        ],
        align="center",
    )
    return


@app.cell
def _(
    button_update_cs,
    carte,
    filtered_gdf,
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
        filtered_gdf.iloc[carte.value[0]["i"]],
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
    filtered_gdf,
    number_ep,
    number_vsav,
    switch_fa,
    switch_fmo,
    switch_ps,
):
    mo.stop(not button_update_cs.value)
    update_gdf(
        filtered_gdf,
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
def _(filtered_gdf):
    df_engins = generation_liste(
        filtered_gdf.drop(columns=["index", "rg_cle", "geometry"])
    )
    df_engins
    return


if __name__ == "__main__":
    app.run()
