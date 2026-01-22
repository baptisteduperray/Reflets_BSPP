from typing import List
from classes import Secteur, Intervention, Engin


def engins_adaptes(secteur: Secteur, intervention: Intervention) -> List[int]:
    df = Engin.df
    mask = (df["cs"].eq(secteur.id)) & (df["intervention_fem_mma"].eq(intervention.fem_mma))
    ids = df.loc[mask, "id"].tolist()          # liste des id
    return ids



def listes_secteur_ordonnes_par_distance(intervention):
    dist = Secteur.df["cs_geometry"].distance(Intervention.df.loc[intervention.id]["geometry"])
    ids_tries = Secteur.df.loc[dist.sort_values().index, "id"].tolist()
    return ids_tries # TODO: verifier que ça marche

