import marimo

__generated_with = "0.15.2"
app = marimo.App(width="full")

with app.setup:
    import pandas as pd
    import polars as pl
    import marimo as mo
    from config import SQLALCHEMY_DATABASE_INFOCENTRE, SQLALCHEMY_DATABASE_INFOREF
    from sqlalchemy import create_engine


@app.cell
def _():
    adagio = create_engine(SQLALCHEMY_DATABASE_INFOREF)
    entrepot = create_engine(SQLALCHEMY_DATABASE_INFOCENTRE)
    return (adagio,)


@app.cell
def _():
    with open("datas/sql/group_by_consecutive_line.sql", "r") as f:
        query = f.read()
    return (query,)


@app.cell
def _(adagio, query):
    indispos = mo.sql(query, engine=adagio)
    return (indispos,)


@app.cell
def _(adagio):
    with open("datas/sql/nombre_affectation_cs.sql", "r") as file:
        aff_query = file.read()
    affectation = mo.sql(aff_query, engine=adagio)
    return


@app.cell
def _(indispos):
    indispos.with_columns(((indispos['fin_indispo'] - indispos['deb_indispo'])).alias('delta_indispo').cast(pl.Duration("ms")))
    return


@app.cell
def _(indispos):
    indispos
    return


if __name__ == "__main__":
    app.run()
