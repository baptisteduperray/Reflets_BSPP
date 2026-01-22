import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import networkx as nx
from . import utils_func

def inter_nodes(
    df_target: pd.DataFrame, df_origin: pd.DataFrame, graph: nx.DiGraph
):
    # TODO bug si aucun engin disponible pour la mission en cours
    # Utile pour le moment pour catch les erreurs dû à la "release" des engins
    # A long terme risque de crash les simulations avec stress fort sur la couvops
    coords2 = np.array(list(zip(df_origin["x"], df_origin["y"])))
    tree = cKDTree(coords2)
    distances, indices = tree.query((df_target["x"], df_target["y"]))
    eng = df_origin[df_origin["cs"] == df_origin.iloc[indices]["cs"]].iloc[0]
    if eng["cs"] == df_target["cs"]:
        return (eng.name, eng["modularite"], 0)
    else:
        try:
            cout = nx.shortest_path_length(
                graph,
                source=eng["node"],
                target=df_target["node"],
                weight="weight",
            )
        except:
            cout = 600
        return (eng.name, eng["modularite"], cout)
    

@utils_func.timer
def load_network():
    nodes = pd.read_csv("datas/reseau/experiment_osm.csv")
    G = nx.DiGraph()

    # itertuples, plus rapide, a utiliser de préférence mais tuple moins pratique que df
    for row in nodes[["from", "to", "cost", "osm_id"]].itertuples(index=False):
        G.add_edge(row[0], row[1], weight=row[2], osm_id=row[3])
    # iterrows, lent mais plus facilement utilisable avec de gros dataset (nom des colonnes conservés)
    # for _, row in nodes[['from','to','cost','osm_id']].iterrows():
    #    G.add_edge(
    #        row['from'], row['to'], weight=row['cost'], osm_id=row['osm_id']
    #    )
    # apply de pandas intermédiaire, noms conservés et rapide
    # nodes[['from','to','cost','osm_id']].apply(lambda row: G.add_edge(
    #       row["from"], row["to"], weight=row["cost"], osm_id=row["osm_id"]
    #   ),axis=1)
    return G