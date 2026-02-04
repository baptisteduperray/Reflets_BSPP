import datetime
from typing import Dict, List

from data import get_data

from classes import Engin, Intervention, Secteur, InterventionSimulee
from statistiques import print_statistiques, combien_de_fois_on_envoie_un_vhl_diff
import filters

# -----------------------------------------------------------------------------
# Interventions, Secteurs et Engins
# -----------------------------------------------------------------------------


def attribuer(intervention: Intervention, secteurs: Dict[str, Secteur], engins: Dict[int, Engin]) -> Engin | None:
    def engin_retenu(secteur: Secteur) -> Engin | None:
        engins_correspondants = filters.engins_adaptes(secteur, intervention)
        # LOGIQUE D'ATTRIBUTION
        engins_correspondants = [engin_id for engin_id in engins_correspondants if engins[engin_id].est_disponible(intervention)]
        engins_correspondants.sort(key=lambda engin_id: engins[engin_id].distance_euclidienne_au_carre(intervention))
        if len(engins_correspondants)>0:
            id = engins_correspondants[0] # TODO: verifier si c'est trie dans le bon ordre
            return engins[id]

    # Cherche si un véhicule est disponible dans le secteur
    engin = engin_retenu(secteurs[intervention.cstc]) # On regarde si dans le secteur cstc il y a un engin dispo
    if engin is not None:
        return engin

    # Si on ne peut pas envoyer de véhicule du secteur, chercher dans les secteurs voisins par distance
    autres_secteurs_ids = filters.listes_secteur_ordonnes_par_distance(intervention)
    for secteur_id in autres_secteurs_ids:
        engin = engin_retenu(secteurs[secteur_id])
        if engin is not None:
            return engin

# ----------------------------------------------------------------------------- #
# Statistiques                                                                  #
# ----------------------------------------------------------------------------- #

interventions_simulees: List[InterventionSimulee] = []  # key: intervention["inter"]

def ajouter_intervention_statistiques(
    engin: Engin,
    temps_trajet: datetime.timedelta,
    intervention: Intervention
):
    interventions_simulees.append(InterventionSimulee.from_Intervention(intervention, engin, temps_trajet))


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

<<<<<<< HEAD
def main():
    interventions, secteurs, engins = get_data()

=======

def main(df_interventions=None, crisis=False, simulation_start=None, simulation_end=None):
    """Run simulation.

    Parameters:
    - df_interventions: optional pandas.DataFrame of interventions (unused currently)
    - crisis: bool, run crisis mode (unused currently)
    - simulation_start, simulation_end: optional datetimes indicating simulation window
    """
    # Note: currently the simulation core reads interventions via get_data().
    # We accept optional parameters for compatibility and future use.
    if simulation_start is not None or simulation_end is not None:
        print(f"Simulation window: {simulation_start} -> {simulation_end}")

    interventions, secteurs, engins = get_data()

    # If a DataFrame of interventions is provided (from uploader), convert it
    # to the internal list[Intervention] format. We handle common column names
    # and try to be robust to missing columns.
    if df_interventions is not None:
        try:
            df = df_interventions.copy()
            # ensure date column is datetime
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            elif "selection" in df.columns:
                df["date"] = pd.to_datetime(df["selection"])

            # ensure numeric time columns exist
            for col in ["retour", "traitement", "trajet", "depart"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            # Build Intervention objects
            interventions = []
            for i, row in df.iterrows():
                try:
                    inter_date = row.get("date")
                    if pd.isna(inter_date):
                        inter_date = pd.Timestamp.now()
                    inter = Intervention(
                        proc=row.get("proc", None),
                        id=row.get("id", i),
                        x=float(row.get("x", 0)),
                        y=float(row.get("y", 0)),
                        x_final=float(row.get("x_final", row.get("x", 0))),
                        y_final=float(row.get("y_final", row.get("y", 0))),
                        retour=datetime.timedelta(seconds=float(row.get("retour", 0))),
                        date=pd.to_datetime(inter_date).to_pydatetime(),
                        traitement=datetime.timedelta(seconds=float(row.get("traitement", 0))),
                        trajet=datetime.timedelta(seconds=float(row.get("trajet", 0))),
                        fem_mma=row.get("fem_mma", ""),
                        cstc=row.get("cstc", ""),
                    )
                    interventions.append(inter)
                except Exception:
                    # skip malformed row
                    continue
        except Exception:
            # If conversion fails, keep interventions from get_data()
            pass

    for _, engin in engins.items():
        secteurs[engin.cs].add_engin(engin)

>>>>>>> d9bb29a (Sauvegarde avant pull)
    i = 0
    print_every = 1000

    for intervention in interventions:
        # Filter by simulation window if provided
        if simulation_start is not None and isinstance(simulation_start, datetime.datetime):
            if intervention.date < simulation_start:
                continue
        if simulation_end is not None and isinstance(simulation_end, datetime.datetime):
            if intervention.date > simulation_end:
                continue
        if intervention.cstc == "NR":
            print("Intervention avec cstc NR")
            continue
        engin = attribuer(intervention, secteurs, engins)
        if engin is not None:
            temps_trajet = engin.attribuer_a(intervention)[0]
            ajouter_intervention_statistiques(engin, temps_trajet, intervention) # TODO: Ici, on a pas encore change la signature, il faut la changer pour la rendre coherante avec la structres de classes
                                                                                    # TODO: Se poser la question d'où ajouter les stats, serait-il pertinant de le faire ailleurs, comme dans la classe engin?
        i += 1
        if i > 10_000:
            break
        if i % print_every == 0:
            print(datetime.datetime.now(), i)

    print("Fini.", i)
    return interventions, engins

if __name__ == "__main__":
    # ---- Toggle profiling by setting USE_PROFILE = True ----
    USE_PROFILE = True
    if USE_PROFILE:
        import cProfile, pstats, io
        pr = cProfile.Profile()
        pr.enable()
        interventions_reelles, engins = main()
        pr.disable()
        print_statistiques(interventions_simulees, engins)
        combien_de_fois_on_envoie_un_vhl_diff(interventions_simulees)
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(40)  # top 40 hotspots
        print(s.getvalue())
    else:
        main()
