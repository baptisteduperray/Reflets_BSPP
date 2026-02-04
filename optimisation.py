
import copy
import pandas as pd
import geopandas as gpd
from data import get_data, get_raw_interventions
from classes import InterventionSimulee, POMPE_Engin, VSAV_Engin, PSE_Engin
from typing import List, Dict
from filters import attribuer
import datetime

# -------------------------------
# 1️⃣ Simulation d'une window
# -------------------------------


def simuler_window_df_engins(
    interventions: List,
    secteurs: Dict[str, any],
    df_engins,
    start_idx: int,
    window_size: int
) -> List[InterventionSimulee]:
    """
    Simule une window d'interventions à partir d'une DataFrame d'engins.
    La DF représente directement l'allocation.
    """

    # Créer des objets Engin propres pour cette simulation
    engins = {}
    for row in df_engins.itertuples():
        if row.type_vhl == "POMPE":
            eng = POMPE_Engin(row.id, row.cs, row.x, row.y)
        elif row.type_vhl == "VSAV":
            eng = VSAV_Engin(row.id, row.cs, row.x, row.y)
        elif row.type_vhl == "PSE":
            eng = PSE_Engin(row.id, row.cs, row.x, row.y)
        else:
            raise ValueError(f"Type d'engin inconnu : {row.type_vhl}")
        engins[row.id] = eng

    interventions_window = interventions[start_idx:start_idx + window_size]
    interventions_simulees: List[InterventionSimulee] = []

    for intervention in interventions_window:
        if intervention.cstc == "NR":
            continue

        engin = attribuer(intervention, secteurs, engins)
        if engin is not None:
            # Calcul du trajet et attribution
            temps_trajet, x_vhl, y_vhl, depart_depuis_caserne = engin.attribuer_a(intervention)

            # Snapshot de l'engin pour éviter les mutations futures
            eng_snapshot = copy.deepcopy(engin)

            # Création de l'intervention simulée
            interventions_simulees.append(
                InterventionSimulee.from_Intervention(
                        intervention,
                        eng_snapshot,
                        temps_trajet
                                )
            )
            

    return interventions_simulees

def eval_window_simple(interventions_simulees: List[InterventionSimulee]) -> float:
    """
    Métrique simplifiée: retourne le temps moyen (en secondes) sur tous les interventions.
    """
    if not interventions_simulees:
        return float('inf')
    
    total_trajet = sum(i.trajet.total_seconds() for i in interventions_simulees)
    return total_trajet / len(interventions_simulees)

def eval_window(interventions_simulees: List[InterventionSimulee], secteurs: Dict[str, any]) -> dict:
    """
    Évalue une window d'interventions et retourne des métriques par CS et un score global.
    """
    cs_metrics = {cs: {} for cs in secteurs.keys()}

    total_trajet = 0
    total_count = 0
    total_couverture_ok = 0
    total_manque_local = 0
    total_rouge_trajet = 0
    total_rouge_count = 0

    inter_cs_dict = {cs: [] for cs in secteurs.keys()}
    for inter in interventions_simulees:
        inter_cs_dict[inter.engin.cs].append(inter)

    for cs, inter_cs in inter_cs_dict.items():
        if not inter_cs:
            cs_metrics[cs] = {k: float('nan') for k in [
                "temps_moyen", "temps_moyen_pompe", "temps_moyen_vsav", "temps_moyen_rouge",
                "taux_couverture"
            ]}
            cs_metrics[cs].update({
                "manque_local": 0,
                "manque_local_pompe": 0,
                "manque_local_vsav": 0,
                "manque_local_rouge": 0,
            })
            continue

        # Temps moyen global
        temps_total = sum(i.trajet.total_seconds() for i in inter_cs)
        count = len(inter_cs)
        temps_moyen = temps_total / count

        # Taux de couverture < seuil
        seuil = 8*60
        taux_couverture = sum(i.trajet.total_seconds() <= seuil for i in inter_cs) / count

        # Manque local (engins venant d'autres CS)
        manque_local = sum(1 for i in inter_cs if i.engin.cs != i.cstc)

        # Manque local par type
        inter_pompe = [i for i in inter_cs if i.fem_mma == "POMPE"]
        inter_vsav = [i for i in inter_cs if i.fem_mma == "VSAV"]
        manque_local_pompe = sum(1 for i in inter_pompe if i.engin.cs != i.cstc)
        manque_local_vsav = sum(1 for i in inter_vsav if i.engin.cs != i.cstc)

        # Procédure rouge
        inter_rouge = [i for i in inter_cs if i.proc == "ROUGE"]
        if inter_rouge:
            temps_moyen_rouge = sum(i.trajet.total_seconds() for i in inter_rouge)/len(inter_rouge)
            manque_local_rouge = sum(1 for i in inter_rouge if i.engin.cs != i.cstc)
        else:
            temps_moyen_rouge = float('nan')
            manque_local_rouge = 0

        cs_metrics[cs] = {
            "temps_moyen": temps_moyen,
            "temps_moyen_pompe": sum(i.trajet.total_seconds() for i in inter_pompe)/len(inter_pompe) if inter_pompe else float("nan"),
            "temps_moyen_vsav": sum(i.trajet.total_seconds() for i in inter_vsav)/len(inter_vsav) if inter_vsav else float("nan"),
            "temps_moyen_rouge": temps_moyen_rouge,
            "taux_couverture": taux_couverture,
            "manque_local": manque_local,
            "manque_local_pompe": manque_local_pompe,
            "manque_local_vsav": manque_local_vsav,
            "manque_local_rouge": manque_local_rouge,
        }

        # Mise à jour global
        total_trajet += temps_total
        total_count += count
        total_couverture_ok += sum(i.trajet.total_seconds() <= seuil for i in inter_cs)
        total_manque_local += manque_local
        if inter_rouge:
            total_rouge_trajet += sum(i.trajet.total_seconds() for i in inter_rouge)
            total_rouge_count += len(inter_rouge)

    # Score global
    TEMPS_REF = 371.367
    TAUX_REF = 0.78066

    if total_count > 0:
        temps_moyen_global = total_trajet / total_count
        taux_couverture_global = total_couverture_ok / total_count
        manque_local_ratio = total_manque_local / total_count

        delta_temps = (temps_moyen_global - TEMPS_REF)/TEMPS_REF
        delta_couv = (TAUX_REF - taux_couverture_global)/TAUX_REF
        delta_manque = manque_local_ratio

        score_val = 0.4*delta_temps + 0.3*delta_couv + 0.3*delta_manque

        if total_rouge_count > 0:
            temps_moyen_rouge = total_rouge_trajet/total_rouge_count
            delta_rouge = (temps_moyen_rouge - TEMPS_REF)/TEMPS_REF
            score_val += 0.3*delta_rouge
        else:
            delta_rouge = None
    else:
        temps_moyen_global = taux_couverture_global = float("nan")
        delta_temps = delta_couv = delta_manque = delta_rouge = None
        score_val = float("nan")

    score_output = {
        "score": score_val,
        "global": {
            "temps_moyen": temps_moyen_global,
            "taux_couverture": taux_couverture_global,
            "manque_local_ratio": total_manque_local/total_count if total_count>0 else float("nan"),
            "total_interventions": total_count,
            "total_rouge_count": total_rouge_count,
        },
        "deltas": {
            "delta_temps": delta_temps,
            "delta_couverture": delta_couv,
            "delta_manque_local": delta_manque,
            "delta_rouge": delta_rouge,
        }
    }

    return {"cs": cs_metrics, "global": score_output}
# -------------------------------
# 3️⃣ Proposer des actions
# -------------------------------
def propose_actions(metrics):
    actions = []
    metrics_cs = metrics["cs"]

    # Manque local rouge
    cs_avec_manque_rouge = [cs for cs, m in metrics_cs.items() if m.get("manque_local_rouge",0) > 0]
    if cs_avec_manque_rouge:
        cs_receveur = max(cs_avec_manque_rouge, key=lambda cs: metrics_cs[cs]["manque_local_rouge"])
        cs_candidates = {cs: m["manque_local_rouge"] for cs, m in metrics_cs.items() if cs not in ["PCDG","ORLY"] and cs != cs_receveur}
        if cs_candidates:
            cs_donneur = min(cs_candidates, key=cs_candidates.get)
            vhl_type = "VSAV" if metrics_cs[cs_receveur].get("manque_local_vsav",0) > 0 else "POMPE"
            actions.append({"type":"deplacement","vhl_type":vhl_type,"cs_from":cs_donneur,"cs_to":cs_receveur,"priorite":"manque_rouge"})

    # Manque local global
    cs_avec_manque = [cs for cs, m in metrics_cs.items() if m.get("manque_local",0) > 0]
    if cs_avec_manque:
        cs_receveur = max(cs_avec_manque, key=lambda cs: metrics_cs[cs]["manque_local"])
        cs_candidates = {cs: m["manque_local"] for cs, m in metrics_cs.items() if cs not in ["PCDG","ORLY"] and cs != cs_receveur}
        if cs_candidates:
            cs_donneur = min(cs_candidates, key=cs_candidates.get)
            vhl_type = "VSAV" if metrics_cs[cs_receveur].get("manque_local_vsav",0)>0 else "POMPE"
            action = {"type":"deplacement","vhl_type":vhl_type,"cs_from":cs_donneur,"cs_to":cs_receveur,"priorite":"manque_local"}
            if not any(a["cs_from"]==action["cs_from"] and a["cs_to"]==action["cs_to"] and a["vhl_type"]==action["vhl_type"] for a in actions):
                actions.append(action)

    # Déséquilibre temps moyen
    cs_sorted_by_time = sorted(metrics_cs.keys(), key=lambda cs: metrics_cs[cs]["temps_moyen"] if not pd.isna(metrics_cs[cs]["temps_moyen"]) else float("inf"))
    cs_min_temps = cs_sorted_by_time[0]
    cs_max_temps = cs_sorted_by_time[-1]
    actions.append({"type":"deplacement","vhl_type":"ANY","cs_from":cs_min_temps,"cs_to":cs_max_temps,"priorite":"temps_moyen"})

    return actions

# -------------------------------
# 4️⃣ Appliquer une action
# -------------------------------
def apply_action(df_engins, action, secteurs):
    df = df_engins.copy(deep=True)
    df["cs"] = df["cs"].astype(str)
    if action["type"] != "deplacement":
        return df, False, "type_action_non_supporte"

    cs_from = str(action["cs_from"])
    cs_to = str(action["cs_to"])
    vhl_type = action["vhl_type"]
    
    if cs_to not in secteurs or cs_from not in secteurs:
        return df, False, "cs_inconnu"

    candidats = df[df["cs"] == cs_from]
    if candidats.empty:
        return df, False, "aucun_vhl_dans_cs_source"

    if vhl_type != "ANY":
        choix = candidats[candidats["type_vhl"]==vhl_type]
        if choix.empty:
            return df, False, "aucun" + vhl_type + "_disponible"
    else:
        choix = candidats
        if choix.empty:
            return df, False, "aucun_vhl_disponible"

    row = choix.sample(1).iloc[0]
    id_vhl = row["id"]

    df.loc[df["id"]==id_vhl,"cs"] = cs_to
    df.loc[df["id"]==id_vhl,"x"] = secteurs[cs_to].x
    df.loc[df["id"]==id_vhl,"y"] = secteurs[cs_to].y
    df.loc[df["id"]==id_vhl,"geometry"] = gpd.points_from_xy([secteurs[cs_to].x],[secteurs[cs_to].y])

    return df, True, "ok"

# -------------------------------
# 5️⃣ Boucle principale sur windows
# -------------------------------
def run_simulation(interventions, secteurs, df_engins_ref, window_size=100000, step=100000, max_interventions=1000000):
    df_courant = df_engins_ref.copy(deep=True)
    stop = min(len(interventions), max_interventions)
    start_idx = 0

    while start_idx < stop:
        print(f"\n==============================\nWindow {start_idx} → {start_idx + window_size}\n==============================")

        inter_sim = simuler_window_df_engins(interventions, secteurs, df_courant, start_idx, window_size)
        print("nb interventions simulées :", len(inter_sim))

        metrics = eval_window(inter_sim, secteurs)
        score_ref = metrics["global"]["score"]
        print(f"Score actuel : {score_ref:.4f}")

        actions = propose_actions(metrics)
        action_appliquee = False

        for action in actions:
            df_test, success, reason = apply_action(df_courant, action, secteurs)
            if not success:
                print(f"Action rejetée ({reason}) :", action)
                continue

            inter_test = simuler_window_df_engins(interventions, secteurs, df_test, start_idx, window_size)
            metrics_test = eval_window(inter_test, secteurs)
            score_test = metrics_test["global"]["score"]
            print(f"Test action {action['priorite']} : score={score_test:.4f}")

            if score_test < score_ref:
                print("✅ Action acceptée :", action)
                df_courant = df_test
                action_appliquee = True
                break

        if not action_appliquee:
            print("❌ Aucune action améliorante sur cette window")

        start_idx += step

    print("\nSimulation terminée.")
    return df_courant


def alloc_optimale(df_engins, interventions, secteurs, window_size=200, step=200):
    """Wrapper that returns an optimized allocation DataFrame.

    It delegates to run_simulation and returns the final DataFrame of engins
    (same schema as input `df_engins`).
    """
    df_final = run_simulation(interventions, secteurs, df_engins, window_size=window_size, step=step)
    return df_final


def run_simulation_optimized(interventions, secteurs, df_engins_ref, window_size=20000, delta_min=0.02, max_interventions=1000000, callback=None):
    """
    Optimized simulation: tracks best allocation found, accepts changes only if improvement >= delta_min.
    
    Args:
        interventions: List of interventions
        secteurs: Dict of sectors
        df_engins_ref: Initial engins allocation
        window_size: Intervention window size (default 20000)
        delta_min: Minimum improvement threshold (default 0.02 = 2%)
        max_interventions: Max interventions to process
        callback: Optional function(data) called at each test with data dict
    
    Returns:
        df_best: Best allocation found during optimization
    """
    df_courant = df_engins_ref.copy(deep=True)
    df_best = df_courant.copy(deep=True)
    
    stop = min(len(interventions), max_interventions)
    start_idx = 0
    
    # Evaluate initial allocation
    inter_sim = simuler_window_df_engins(interventions, secteurs, df_courant, 0, window_size)
    score_best = eval_window_simple(inter_sim)
    print(f"Score initial: {score_best:.2f}s")
    
    if callback:
        callback({
            "type": "init",
            "score_initial": score_best,
            "score_best": score_best
        })
    
    iteration = 0
    total_windows = (stop + window_size - 1) // window_size
    
    while start_idx < stop:
        iteration += 1
        window_num = iteration
        print(f"\n{'='*50}\nWindow {start_idx} → {min(start_idx + window_size, stop)}\n{'='*50}")
        
        if callback:
            callback({
                "type": "window_start",
                "window": window_num,
                "total_windows": total_windows,
                "progress": window_num / total_windows
            })
        
        inter_sim = simuler_window_df_engins(interventions, secteurs, df_courant, start_idx, window_size)
        score_ref = eval_window_simple(inter_sim)
        print(f"Score courant: {score_ref:.2f}s")
        
        actions = propose_actions(eval_window(inter_sim, secteurs))
        action_appliquee = False
        
        for action_idx, action in enumerate(actions):
            df_test, success, reason = apply_action(df_courant, action, secteurs)
            if not success:
                print(f"Action rejetée ({reason}): {action}")
                continue
            
            inter_test = simuler_window_df_engins(interventions, secteurs, df_test, start_idx, window_size)
            score_test = eval_window_simple(inter_test)
            
            # Calculate improvement ratio
            improvement_ratio = (score_ref - score_test) / score_ref if score_ref > 0 else 0
            
            print(f"Test {action['priorite']}: score={score_test:.2f}s (delta={improvement_ratio*100:.2f}%)", end="")
            
            if callback:
                callback({
                    "type": "action_test",
                    "window": window_num,
                    "action_name": action['priorite'],
                    "action_idx": action_idx + 1,
                    "score_test": score_test,
                    "delta_pct": improvement_ratio * 100,
                    "delta_min_pct": delta_min * 100,
                    "status": "testing"
                })
            
            # Accept only if improvement >= delta_min
            if improvement_ratio >= delta_min:
                print(" ✅ ACCEPTÉE")
                df_courant = df_test
                action_appliquee = True
                
                if callback:
                    callback({
                        "type": "action_accepted",
                        "window": window_num,
                        "action_name": action['priorite'],
                        "score_test": score_test,
                        "delta_pct": improvement_ratio * 100
                    })
                
                # Update best if this is better overall
                if score_test < score_best:
                    df_best = df_test.copy(deep=True)
                    score_best = score_test
                    print(f"🎯 NOUVEAU BEST: {score_best:.2f}s")
                    
                    if callback:
                        callback({
                            "type": "new_best",
                            "window": window_num,
                            "score_best": score_best
                        })
                break
            else:
                print(f" ❌ insuffisant")
                if callback:
                    callback({
                        "type": "action_rejected",
                        "window": window_num,
                        "action_name": action['priorite'],
                        "score_test": score_test,
                        "delta_pct": improvement_ratio * 100
                    })
        
        if not action_appliquee:
            print("❌ Aucune action améliorante")
            if callback:
                callback({
                    "type": "no_action",
                    "window": window_num,
                    "score_best": score_best
                })
        
        start_idx += window_size  # Non-overlapping windows
    
    print(f"\n{'='*50}\nOptimisation terminée.\nScore final: {score_best:.2f}s\n{'='*50}")
    
    if callback:
        callback({
            "type": "finished",
            "score_best": score_best
        })
    
    return df_best


if __name__ == "__main__":
    
    # --- Charger les données
    interventions, secteurs, engins_dict = get_data()
   
    df_engins = pd.DataFrame([{
        "id": eng.id,
        "cs": eng.cs,
        "x": eng.x(datetime.datetime.min)[0],  
        "y": eng.y(datetime.datetime.min)[0],
        "type_vhl" : eng.type_engin
    } for eng in engins_dict.values()])

    # Colonne geometry
    df_engins["geometry"] = gpd.points_from_xy(df_engins["x"], df_engins["y"])
    df_engins = gpd.GeoDataFrame(df_engins, geometry="geometry")

        #  Ajouter la colonne geometry
    df_engins["geometry"] = gpd.points_from_xy(df_engins["x"], df_engins["y"])


    # Transformer en GeoDataFrame
    df_engins = gpd.GeoDataFrame(df_engins, geometry="geometry")

    # --- Tester l'optimisation sur une petite fenêtre pour debug
    # --- Tester l'optimisation sur une petite fenêtre pour debug
    window_size = 50  # petit pour test rapide
    step = 50

    print("🔹 Début test optimisation")
    df_final = run_simulation(interventions, secteurs, df_engins, window_size=window_size, step=step)
    print("🔹 Simulation terminée")

    # --- Affichage métriques finales
    inter_sim = simuler_window_df_engins(interventions, secteurs, df_final, start_idx=0, window_size=window_size)
    metrics = eval_window(inter_sim, secteurs)

    print("Score global final :", metrics["global"]["score"])
    print("Metrics par CS (exemple) :", list(metrics["cs"].items())[:2])

    # --- Répartition finale des engins
    print("Répartition finale des engins :")
    print(df_final[["id", "cs", "x", "y", "type_vhl"]].head())

    # --- Optionnel : visualisation rapide des positions
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))
    df_final.plot(ax=ax, color="blue", markersize=50)
    for idx, row in df_final.iterrows():
        ax.text(row["x"], row["y"], f"{row['id']}:{row['type_vhl']}", fontsize=8)
    plt.title("Positions finales des engins après optimisation")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.show()
