import data
from classes import InterventionSimulee, Intervention, Engin
from typing import List, Dict
import datetime
import pandas as pd

def print_statistiques(interventions_simulees: List[InterventionSimulee], engins: Dict[int, Engin]):
    print_trajet_moyen(interventions_simulees)
    print_taux_utilisation_par_engin(interventions_simulees, engins)

def print_taux_utilisation_par_engin(interventions: List[InterventionSimulee], engins: Dict[int, Engin]):
    temps_dehors_dict = {}
    for index, engin in engins.items():
        temps_dehors = datetime.timedelta()
        for i in range(engin.nombre_de_sorties()):
            delta = (engin.temps_de_retour_a_la_caserne[i] - engin.temps_de_sorties_de_la_caserne[i])
            assert delta >= datetime.timedelta()
            temps_dehors += delta
        temps_dehors_dict[index] = temps_dehors

    temps_de_simulation = interventions[-1].date - interventions[0].date # Approximation

    taux_utilisation = {index : temps_dehors/temps_de_simulation for index, temps_dehors in temps_dehors_dict.items()}

    for index, taux in taux_utilisation.items():
        print(f"index={index}, taux={taux:.2f}")

def print_trajet_moyen(interventions_simulees: List[InterventionSimulee]):
    trajet_moyen = datetime.timedelta(0)
    for intervention in interventions_simulees:
        trajet_moyen += intervention.trajet
    trajet_moyen /= len(interventions_simulees)
    print(f"{trajet_moyen.total_seconds():.2f} seconds")

def interventions_simulees_to_df(interventions_simulees):
    rows = []

    for inter in interventions_simulees:
        engin = inter.engin

        # Position de l'engin à la date du départ
        x_vhl = engin.x(inter.date)
        y_vhl = engin.y(inter.date)

        rows.append({
            "id_inter": inter.id,
            "x_inter": inter.x,
            "y_inter": inter.y,
            "id_vhl": engin.id,
            "x_vhl": x_vhl,
            "y_vhl": y_vhl,
            "cs_vhl": engin.cs,
            "temps_trajet_s": inter.trajet.total_seconds(),
            "date_inter": inter.date,
            "secteur": inter.cstc,
            "urgence": inter.proc,
            "type": inter.fem_mma,  # ou bool selon tes besoins
        })

    return pd.DataFrame(rows)


def calculer_metriques(df):
    """
    df : DataFrame retourné par interventions_simulees_to_df
    """

    # --- Métriques globales ---
    temps_moyen_trajet = df["temps_trajet_s"].mean()

    # --- Par CSTC ---
    temps_moyen_par_cstc = df.groupby("secteur")["temps_trajet_s"].mean()

    # --- Par degré d’urgence ---
    temps_moyen_par_urgence = df.groupby("urgence")["temps_trajet_s"].mean()

    # --- Nombre d'interventions où l'engin vient d'un autre centre ---
    nb_mauvais_cstc = (df["secteur"] != df["cs_vhl"]).sum()

    # --- Organise tout dans un dict lisible ---
    return {
        "temps_moyen_trajet_s": temps_moyen_trajet,
        "temps_moyen_par_cstc": temps_moyen_par_cstc.to_dict(),
        "temps_moyen_par_urgence": temps_moyen_par_urgence.to_dict(),
        "nb_interventions_mauvais_cstc": nb_mauvais_cstc,
    }


def combien_de_fois_on_envoie_un_vhl_diff(interventions_simulees):
    inter_réelle = data.get_raw_interventions()

    df_sim = interventions_simulees_to_df(interventions_simulees)

    # 2️⃣ Merge avec les données réelles
    # inter_reelle doit avoir au moins les colonnes : 'inter' et 'cs'
    df_merge = pd.merge(
        df_sim,
        inter_réelle,
        left_on="id_inter",
        right_on="inter_id",
        how="inner"
    )

    # 3️⃣ Compter le nombre de désaccords entre le CSTC de l'engin simulé et le CSTC réel
    nb_mauvais_cstc = (df_merge["cs_vhl"] != df_merge["cs"]).sum()
    mauvais_cstc = (df_merge["cs_vhl"] != df_merge["cs"])

    print(f"Nombre d'interventions où le véhicule simulé vient d'un autre CSTC : {nb_mauvais_cstc}")
    return nb_mauvais_cstc



