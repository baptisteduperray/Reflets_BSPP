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

def main():
    interventions, secteurs, engins = get_data()

    i = 0
    print_every = 1000

    for intervention in interventions:
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
