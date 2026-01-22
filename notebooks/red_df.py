import marimo

__generated_with = "0.15.2"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    import numpy as np
    from sqlalchemy import create_engine, text
    from config import (
        INTERVENTIONS,
        RED,
        SQLALCHEMY_DATABASE_INFOREF,
        SQLALCHEMY_DATABASE_INFOCENTRE,
        LIEN_RED_INTER,
    )


@app.cell
def _():
    adagio = create_engine(SQLALCHEMY_DATABASE_INFOREF)
    entrepot = create_engine(SQLALCHEMY_DATABASE_INFOCENTRE)
    return (adagio,)


@app.cell
def _():
    red_df = pd.read_csv(RED)
    red_df = red_df[red_df.IdInterventionSolution != 4287]  # Rondes
    red = mo.ui.table(red_df, selection="single")
    return (red_df,)


@app.cell
def _(red_df):
    formatted_red = (
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
    update_red = mo.ui.data_editor(formatted_red)
    return formatted_red, update_red


@app.cell
def _(update_red):
    mo.accordion({"RED": update_red})
    return


@app.cell
def _(df, update_red):
    pd.merge(
        df[
            [
                "inter",
                "IdInterventionSolution",
                "CodeClasseFamilleMateriel",
                "IdMMASelection",
            ]
        ]
        .groupby(["inter", "IdInterventionSolution", "CodeClasseFamilleMateriel"])
        .count()
        .reset_index(),
        update_red.value,
        on="IdInterventionSolution",
    )
    return


@app.cell
def _(update_red):
    update_red
    return


@app.cell
def _(formatted_red, update_red):
    merged = pd.merge(
        formatted_red,
        update_red.value[["IdInterventionSolution", "EP", "FA", "FMOGP", "VSAV"]],
        on="IdInterventionSolution",
        suffixes=("", "_m"),
    )

    merged['delta_FMOGP'] = merged['FMOGP'] - merged['FMOGP_m']
    merged['delta_FA'] = merged['FA'] - merged['FA_m']
    merged['delta_EP'] = merged['EP'] - merged['EP_m']
    merged['delta_VSAV'] = merged['VSAV'] - merged['VSAV_m']
    merged['delta_total'] = merged['delta_FMOGP'] + merged['delta_FA'] + merged['delta_EP'] + merged['delta_VSAV']
    return (merged,)


@app.cell
def _():
    # TODO paramétrage RED: retirer nième engin du genre ou ajouter un faux départ du type d'engin
    pass
    return


@app.cell
def _(lien):
    df = pd.read_csv(INTERVENTIONS)
    df = pd.merge(df, lien, on="IdMMASelection", how="left").fillna(
        {"IdInterventionSolution": -1}
    )
    return (df,)


@app.cell
def _(df):
    df
    return


@app.cell
def _(df):
    listing_fmofa = df[["inter", "IdInterventionSolution", "fam_engin", "engagement"]].groupby(
        ["inter", "IdInterventionSolution", "fam_engin"]
    ).count().reset_index().pivot(index=['inter','IdInterventionSolution'],columns='fam_engin',values='engagement')[['FMOGP','FA']].dropna(how='all').reset_index()
    listing_fmofa = listing_fmofa[listing_fmofa['IdInterventionSolution'] != -1].fillna(0)
    return (listing_fmofa,)


@app.cell
def _(listing_fmofa, merged):
    fmofa_red = merged[merged['delta_total'] > 0][['LibelleMotifAlerte','IdInterventionSolution','FA','FMOGP','delta_FA','delta_FMOGP']]
    pd.merge(fmofa_red,listing_fmofa,on=['IdInterventionSolution'],how='inner')
    return


@app.cell
def _(df):
    df[df["IdInterventionSolution"] != -1]
    return


@app.cell
def _(df):
    np.where(
        (df["fem_mma"] == "VSAV") & (df["IdInterventionSolution"] == 24170),
        "POMPE",
        df["fem_mma"],
    )
    return


@app.cell
def _(formatted_red):
    formatted_red
    return


@app.cell
def _(df, formatted_red):
    df[(df['IdInterventionSolution'].isin(formatted_red[(formatted_red['EP'] > 0) & (formatted_red['VSAV'] == 0)]['IdInterventionSolution'])) & (df['fem_mma'] == 'VSAV')]
    return


@app.cell
def _(df):
    df["fem_mma"].where(
        ~((df["fem_mma"] == "VSAV") & (df["IdInterventionSolution"] == 24170)),
        "POMPE",
    )
    return


@app.cell
def _(df):
    df[["inter", "IdInterventionSolution", "fam_engin", "IdMMASelection"]].groupby(
        ["inter", "IdInterventionSolution", "fam_engin"]
    ).count().reset_index()
    return


@app.cell
def _(df):
    df[["inter", "IdInterventionSolution", "fem_mma", "IdMMASelection"]].groupby(
        ["inter", "IdInterventionSolution", "fem_mma"]
    ).count().reset_index()
    return


@app.cell(hide_code=True)
def _(adagio):
    try:
        lien = pd.read_csv(LIEN_RED_INTER)
    except:
        with open("datas/sql/sel_red.sql", "r") as f:
            query = f.read()
        lien = mo.sql(query, engine=adagio).to_pandas()
    return (lien,)


@app.cell
def _(inter):
    inter
    return


@app.cell
def _():
    inter = pd.read_csv(INTERVENTIONS)
    return (inter,)


@app.cell
def _():
    with open("datas/sql/sel_red.sql", "r") as file:
        requete = file.read()
    # mo.sql(requete,engine=adagio).write_csv(LIEN_RED_INTER)
    return


if __name__ == "__main__":
    app.run()
