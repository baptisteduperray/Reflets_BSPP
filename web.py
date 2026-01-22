import marimo

__generated_with = "0.17.8"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import geopandas as gpd
    import folium
    import csv
    import os
    from data import get_engins as get_engins_data, get_secteurs
    from main import main
    return csv, folium, get_engins_data, get_secteurs, gpd, main, mo


@app.cell
def _(get_engins_data, get_secteurs, mo):
    secteurs_initiaux = get_secteurs()
    engins_initiaux = get_engins_data()

    get_engins, set_engins = mo.state([
        {"id": e, "cs": engins_initiaux[e].cs, "nom": f"{engins_initiaux[e]}"}
        for e in engins_initiaux
    ])
    return get_engins, secteurs_initiaux, set_engins


@app.cell
def _(gpd):
    GEOJSON_PATH = "datas/geo/secteurs_cs.geojson"
    gdf = gpd.read_file(GEOJSON_PATH)
    return (gdf,)


@app.cell
def _(folium, gdf, get_engins, mo):
    _engins = get_engins()
    counts = {}
    engins_by_sector = {}
    for _e in _engins:
        sid = _e["cs"]
        counts[sid] = counts.get(sid, 0) + 1
        engins_by_sector.setdefault(sid, []).append(_e["nom"])

    m = folium.Map(location=[48.8566, 2.3522], zoom_start=9)

    def style(f):
        sid = f["properties"]["nom"]
        n = counts.get(sid, 0)
        if n == 0:
            color = "#CCCCCC"
        elif n < 3:
            color = "#7ED957"
        else:
            color = "#FF6B6B"
        return {
            "fillColor": color,
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.6,
        }

    # attach engin names to each GeoDataFrame row so tooltip can show them
    try:
        gdf2 = gdf.copy()
        gdf2["engins"] = gdf2["nom"].map(lambda s: ", ".join(engins_by_sector.get(s, [])) or "—")
    except Exception:
        gdf2 = gdf

    folium.GeoJson(
        gdf2,
        style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=["nom", "engins"], aliases=["Secteur", "Engins"])
    ).add_to(m)

    carte = mo.Html(m._repr_html_())

    carte
    return


@app.cell
def _(csv, get_engins, mo, secteurs_initiaux, set_engins):
    _engins = get_engins()

    options_engins = {
        f"{_e['nom']} – {_e['cs']}": _e["id"] for _e in _engins
    }
    engin_select = mo.ui.dropdown(
        label="Choisir engin",
        options=options_engins,
        value=next(iter(options_engins.keys())),
        searchable=True
    )

    options_secteurs = {s: s for s in secteurs_initiaux}
    secteur_select = mo.ui.dropdown(
        label="Nouveau secteur",
        options=options_secteurs,
        value=None
    )

    def move():
        eid = engin_select.value
        sid = secteur_select.value

        rows = []
        found = False

        # Lire le fichier existant s'il existe
        with open("datas/utils/modifications_engins.csv", mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["id"] == str(eid):
                    row["cs"] = str(sid)
                    found = True
                rows.append(row)

        # Si l'id n'existe pas, on ajoute une ligne
        if not found:
            rows.append({"id": str(eid), "cs": str(sid)})

        # Réécriture du fichier
        with open("datas/utils/modifications_engins.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "cs"])
            writer.writeheader()
            writer.writerows(rows)

        def update(lst):
            new = []
            for _e in lst:
                if _e["id"] == eid:
                    new.append({**_e, "cs": sid})
                else:
                    new.append(_e)
            return new

        set_engins(update)

    bouton = mo.ui.button(label="Déplacer", on_click=lambda _: move())
    return bouton, engin_select, secteur_select


@app.cell
def _(bouton, engin_select, get_engins, mo, secteur_select, secteurs_initiaux):
    _engins = get_engins()

    by_sec = {s: [] for s in secteurs_initiaux}
    for _e in _engins:
        by_sec[_e["cs"]].append(_e["nom"])

    data = {
        "Secteur": [s for s in secteurs_initiaux],
        "Engins": [", ".join(by_sec[s]) or "—" for s in secteurs_initiaux]
    }

    table = mo.ui.table(data, pagination=False, selection=None)

    ui = mo.vstack(
        [
            mo.md("### Déplacement d’engins entre secteurs"),
            mo.hstack([engin_select, secteur_select, bouton]),
            mo.md("### Répartition actuelle des engins par secteur"),
            table,
        ]
    )

    ui
    return


@app.cell
def _(main, mo):
    get_progress, set_progress = mo.state(0)
    def run_simulation():
        main()
        set_progress(1)
    mo.ui.button(label="Lancer une simulation", on_click=lambda _: run_simulation())
    return (get_progress,)


@app.cell
def _(get_progress, mo):
    if get_progress() == 0:
        text = "Simulation non terminée"
    else:
        text = "Simulation terminée"
    mo.ui.text(text)
    return


@app.cell
def _(folium, gdf, get_progress, mo):
    stat_map = folium.Map(location=[48.8566, 2.3522], zoom_start=9)

    if get_progress() == 1:
        from main import interventions_simulees
        import datetime

        def get_stat(cs):
            interventions_cs = [intervention for intervention in interventions_simulees if intervention.cstc == cs]
            temps_moyen = sum([intervention.trajet for intervention in interventions_cs], start=datetime.timedelta(0)) / len(interventions_cs) if len(interventions_cs) > 0 else datetime.timedelta(0)
            return temps_moyen
        
        def style_stat(temps):
            return f"{int(temps.seconds / 60)} min {temps.seconds % 60} sec"
        
        # attach engin names to each GeoDataFrame row so tooltip can show them
        stat_gdf = gdf.copy()
        temps = stat_gdf["nom"].map(get_stat)
        temps_min = temps.min()
        temps_max = temps.max()

        def stat_style(f):
            def color(l):
                # Gradient from green (low) to red (high)
                r = int(255 * l)
                g = int(255 * (1 - l))
                b = 0
                return f"#{r:02X}{g:02X}{b:02X}"
            cs = f["properties"]["nom"]
            return {
                "fillColor": color((get_stat(cs).seconds - temps_min.seconds) / (temps_max.seconds - temps_min.seconds)),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.6,
            }

        stat_gdf["stat"] = temps.map(style_stat)

        folium.GeoJson(
            stat_gdf,
            style_function=stat_style,
            tooltip=folium.GeoJsonTooltip(fields=["nom", "stat"], aliases=["Secteur", "Temps moyen (min:sec)"])
        ).add_to(stat_map)

    stat_carte = mo.Html(stat_map._repr_html_())

    stat_carte
    return


if __name__ == "__main__":
    app.run()
