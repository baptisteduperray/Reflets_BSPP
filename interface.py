import os
import streamlit as st
import geopandas as gpd
import folium
import pandas as pd
import datetime
import numpy as np
from main import main  # ton simulateur Marimo
from data import get_engins as get_engins_data, get_secteurs
from streamlit_folium import st_folium
from classes import POMPE, PSE, VSAV
import plotly.graph_objects as go

from data import get_raw_engins, get_interventions
import optimisation as opt
# -----------------------------
# SET GDAL DATA (pour éviter warning)
# -----------------------------
os.environ["GDAL_DATA"] = r"C:\Users\baptd\anaconda3\envs\marimo_env\Library\share\gdal"

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide")
st.title("Simulateur Marimo - Paris")

# -----------------------------
# STATE INITIALIZATION
# -----------------------------
if "engins" not in st.session_state:
    engins_initiaux = get_engins_data()
    st.session_state.engins = [
        {
            "id": e,
            "cs": engins_initiaux[e].cs,
            "nom": f"{engins_initiaux[e]}",
            "type": engins_initiaux[e].type_engin,
        }
        for e in engins_initiaux
    ]

if "engins_initial" not in st.session_state:
    st.session_state.engins_initial = [dict(eng) for eng in st.session_state.engins]

if "progress" not in st.session_state:
    st.session_state.progress = 0

if "allocation_dirty" not in st.session_state:
    st.session_state.allocation_dirty = False

# -----------------------------
# LOAD SECTEURS
# -----------------------------
secteurs_initiaux = get_secteurs()
GEOJSON_PATH = "datas/geo/secteurs_cs.geojson"
gdf = gpd.read_file(GEOJSON_PATH)

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("⚙️ Paramètres")

# Paramètre: durée de simulation (date début / date fin)
date_range = st.sidebar.date_input(
    "Durée de simulation (début, fin)",
    value=[datetime.date.today(), datetime.date.today()]
)
# Normaliser la valeur renvoyée par st.date_input :
# - peut être une date unique, ou une liste/tuple de deux éléments
# - pendant la sélection, l'un des éléments peut être None
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    sim_start_date, sim_end_date = date_range
else:
    sim_start_date = sim_end_date = date_range

# Normalisation robuste des valeurs retournées par st.date_input
def _to_date(d):
    # handle None
    if d is None:
        return None
    # if passed as (date,) or [date]
    if isinstance(d, (list, tuple, np.ndarray)):
        if len(d) == 0:
            return None
        d = d[0]
    # pandas / numpy types
    try:
        if isinstance(d, pd.Timestamp):
            return d.date()
    except Exception:
        pass
    try:
        if isinstance(d, (np.datetime64,)):
            return pd.to_datetime(d).date()
    except Exception:
        pass
    # datetime -> date
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    # fallback: try to parse
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

sim_start_date = _to_date(sim_start_date)
sim_end_date = _to_date(sim_end_date)

# Gérer les cas où l'utilisateur n'a sélectionné qu'une seule date
if sim_start_date is None and sim_end_date is None:
    sim_start_date = sim_end_date = datetime.date.today()
elif sim_start_date is None:
    sim_start_date = sim_end_date
elif sim_end_date is None:
    sim_end_date = sim_start_date

st.session_state["simulation_start"] = datetime.datetime.combine(sim_start_date, datetime.time.min)
st.session_state["simulation_end"] = datetime.datetime.combine(sim_end_date, datetime.time.max)

# --- Upload CSV interventions ---
# Uploader unique placé dans la zone principale, dans un expander
st.markdown("### Chargement des interventions")
with st.expander("Upload CSV d'interventions (optionnel)", expanded=True):
    uploaded_file = st.file_uploader("Choisir un CSV", type=["csv"])    
    if uploaded_file:
        try:
            df_interventions = pd.read_csv(uploaded_file)
            st.success(f"{len(df_interventions)} lignes chargées")
        except Exception as e:
            st.error(f"Erreur lecture CSV: {e}")
            df_interventions = None
    else:
        df_interventions = None

# --- Boutons simulation ---
st.sidebar.markdown("---")
st.sidebar.subheader("Simulations")

# Check if current engins match initial state (only if not already marked dirty)
if not st.session_state.allocation_dirty:
    engins_current_sorted = sorted(st.session_state.engins, key=lambda e: e["id"])
    engins_initial_sorted = sorted(st.session_state.engins_initial, key=lambda e: e["id"])
    if engins_current_sorted != engins_initial_sorted:
        st.session_state.allocation_dirty = True

# Optimiser button
if st.session_state.allocation_dirty:
    st.sidebar.markdown("<div style='background:#ff4444;padding:6px;border-radius:6px;text-align:center;color:white'><b>Allocation modifiée — optimiser recommandée</b></div>", unsafe_allow_html=True)
if st.sidebar.button("Optimiser (recalcul allocation)"):
    try:
        df_raw = get_raw_engins()
    except Exception as e:
        st.error(f"Impossible de charger les engins bruts: {e}")
        df_raw = None
    if df_raw is not None:
        df = df_raw.copy()
        if "Type_VHL" in df.columns:
            df["type_vhl"] = df["Type_VHL"]
        if "type_vhl" not in df.columns:
            df["type_vhl"] = df["id"].map({e["id"]: e.get("type") for e in st.session_state.engins}).fillna("UNKNOWN")
        for e in st.session_state.engins:
            df.loc[df["id"] == e["id"], "cs"] = e["cs"]
            if e["cs"] in secteurs_initiaux:
                df.loc[df["id"] == e["id"], "x"] = secteurs_initiaux[e["cs"]].x
                df.loc[df["id"] == e["id"], "y"] = secteurs_initiaux[e["cs"]].y
        try:
            interventions = get_interventions()
            sim_start = st.session_state.get("simulation_start")
            sim_end = st.session_state.get("simulation_end")
            if sim_start or sim_end:
                interventions = [i for i in interventions if (sim_start is None or i.date >= sim_start) and (sim_end is None or i.date <= sim_end)]
        except Exception as e:
            st.error(f"Impossible de charger les interventions: {e}")
            interventions = []
        
        # ===== INTERFACE DE SUIVI =====
        st.markdown("---")
        st.markdown("## ⚙️ Optimisation en cours...")
        
        # Placeholders
        progress_ph = st.empty()
        metrics_ph = st.empty()
        action_ph = st.empty()
        chart_ph = st.empty()
        table_ph = st.empty()
        
        # Historique et données de tracking
        history = []
        scores_best = []
        window_numbers = []
        actions_count = {"tested": 0, "accepted": 0}
        score_initial = None
        score_best = None
        
        def update_callback(data):
            nonlocal history, score_initial, score_best, window_numbers, scores_best, actions_count
            
            if data["type"] == "init":
                score_initial = data["score_initial"]
                score_best = data["score_best"]
                with progress_ph:
                    st.info(f"Score initial: {score_initial:.0f}s")
            
            elif data["type"] == "window_start":
                window_num = data["window"]
                progress = data["progress"]
                with progress_ph:
                    st.progress(progress, text=f"Window {window_num} / {data['total_windows']}")
            
            elif data["type"] == "action_test":
                actions_count["tested"] += 1
                with action_ph:
                    delta_text = f"Δ{data['delta_pct']:+.1f}%"
                    if data['delta_pct'] >= data['delta_min_pct']:
                        st.success(f"🧪 Test: {data['action_name']} → {data['score_test']:.0f}s ({delta_text}) ✅")
                    else:
                        st.warning(f"🧪 Test: {data['action_name']} → {data['score_test']:.0f}s ({delta_text}) ❌")
            
            elif data["type"] == "action_accepted":
                actions_count["accepted"] += 1
                history.append({
                    "window": data["window"],
                    "action": data["action_name"],
                    "delta%": data["delta_pct"],
                    "status": "✅ Acceptée"
                })
            
            elif data["type"] == "action_rejected":
                history.append({
                    "window": data["window"],
                    "action": data["action_name"],
                    "delta%": data["delta_pct"],
                    "status": "❌ Rejetée"
                })
            
            elif data["type"] == "new_best":
                score_best = data["score_best"]
                window_numbers.append(data["window"])
                scores_best.append(score_best)
                with action_ph:
                    st.success(f"🎯 NOUVEAU BEST: {score_best:.0f}s")
            
            elif data["type"] == "no_action":
                with action_ph:
                    st.info(f"❌ Aucune action améliorante (Window {data['window']})")
            
            elif data["type"] == "finished":
                score_best = data["score_best"]
            
            # Mettre à jour les métriques
            with metrics_ph:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Initial", f"{score_initial:.0f}s" if score_initial else "—")
                with col2:
                    st.metric("Actions", f"{actions_count['accepted']} / {actions_count['tested']}")
                with col3:
                    st.metric("Best", f"{score_best:.0f}s" if score_best else "—", 
                             f"{((score_initial - score_best) / score_initial * 100):.1f}%" if score_initial and score_best else "—")
            
            # Mettre à jour le graphique
            if scores_best:
                with chart_ph:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=window_numbers,
                        y=scores_best,
                        mode='lines+markers',
                        name='Best Score',
                        line=dict(color='red', width=2),
                        marker=dict(size=8)
                    ))
                    if score_initial:
                        fig.add_hline(y=score_initial, line_dash="dash", line_color="blue", 
                                     annotation_text="Initial", annotation_position="right")
                    fig.update_layout(
                        title="Évolution du meilleur score par window",
                        xaxis_title="Window",
                        yaxis_title="Temps moyen (s)",
                        height=300,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Mettre à jour le tableau
            if history:
                with table_ph:
                    st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        
        # Lancer l'optimisation
        with st.spinner("Optimisation en cours..."):
            try:
                df_final = opt.run_simulation_optimized(
                    interventions, 
                    secteurs_initiaux, 
                    df, 
                    window_size=20000, 
                    delta_min=0.02,
                    callback=update_callback
                )
            except Exception as e:
                st.error(f"Erreur optimisation: {e}")
                df_final = None
        
        if df_final is not None:
            id_to_cs = {row["id"]: row["cs"] for _, row in df_final.iterrows()}
            for e in st.session_state.engins:
                if e["id"] in id_to_cs:
                    e["cs"] = id_to_cs[e["id"]]
            st.success("✅ Allocation optimisée et appliquée.")
            st.rerun()

if st.sidebar.button("Simulation passée (2023)"):
    # Passer la période de simulation à main
    sim_start = st.session_state.get("simulation_start")
    sim_end = st.session_state.get("simulation_end")
    if df_interventions is not None:
        main(df_interventions=df_interventions, simulation_start=sim_start, simulation_end=sim_end)
    else:
        main(simulation_start=sim_start, simulation_end=sim_end)
    st.session_state.progress = 1
    st.success("Simulation passée terminée !")

if st.sidebar.button("Simulation de crise"):
    sim_start = st.session_state.get("simulation_start")
    sim_end = st.session_state.get("simulation_end")
    main(crisis=True, simulation_start=sim_start, simulation_end=sim_end)
    st.session_state.progress = 1
    st.success("Simulation de crise terminée !")

# --- Gestion des engins ---
st.sidebar.markdown("---")
st.sidebar.subheader("Gestion des engins")

if st.sidebar.button("♾️ Reset (allocation initiale)"):
    st.session_state.engins = [dict(eng) for eng in st.session_state.engins_initial]
    st.session_state.allocation_dirty = False
    st.success("Allocation réinitialisée.")
    st.rerun()

engins_base = get_engins_data()
types_vhl = [POMPE, PSE, VSAV]

for vhl_type in types_vhl:
    # Calculer le nombre actuel
    count = sum(1 for e in st.session_state.engins if e.get("type") == vhl_type)

    # Carte compacte dans la sidebar
    card = st.sidebar.container()
    with card:
        # Mettre le type en évidence avec un petit header et emoji
        st.markdown(f"### 🚒 {vhl_type}")
        cols = st.columns([1, 2])
        with cols[0]:
            st.metric(label="Nombre", value=count)
        with cols[1]:
            # Boutons côte à côte plus visibles
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("➖ Retirer", key=f"btn_minus_{vhl_type}"):
                    for i, e in enumerate(st.session_state.engins):
                        if e.get("type") == vhl_type:
                            st.session_state.engins.pop(i)
                            st.session_state.allocation_dirty = True
                            st.rerun()
            with bcol2:
                if st.button("➕ Ajouter", key=f"btn_plus_{vhl_type}"):
                    existing_ids = {e["id"] for e in st.session_state.engins}
                    chosen_cs = "ANTO"
                    for e_id in engins_base:
                        obj = engins_base[e_id]
                        if obj.type_engin == vhl_type and e_id not in existing_ids:
                            st.session_state.engins.append({
                                "id": e_id,
                                "cs": chosen_cs,
                                "nom": str(obj),
                                "type": vhl_type
                            })
                            st.session_state.allocation_dirty = True
                            st.rerun()
                            break

# -----------------------------
# DISPLAY ENGINS TABLE AVEC SLIDER
# -----------------------------


# Sidebar optimiser button removed (moved to Simulations section above)

st.subheader("Tableau détaillé des engins")
num_vhl = st.slider(
    "Nombre d'engins à afficher", 
    min_value=1, 
    max_value=len(st.session_state.engins), 
    value=min(10, len(st.session_state.engins))
)
engins_df = pd.DataFrame(st.session_state.engins)
st.dataframe(engins_df.head(num_vhl), width='stretch')

# -----------------------------
# AJOUTER UN ENGINS + OPTIMISATION
# -----------------------------
st.markdown("---")
st.write("")

col_type, col_cs, col_run = st.columns([1, 2, 1])
with col_type:
    add_type = None
with col_cs:
    choix_cs = None
with col_run:
    run_opt = False  # central panel disabled; use sidebar Optimiser

if run_opt:
    try:
        df_raw = get_raw_engins()
    except Exception as e:
        st.error(f"Impossible de charger les engins bruts: {e}")
        df_raw = None

    if df_raw is not None:
        df = df_raw.copy()
        if "Type_VHL" in df.columns:
            df["type_vhl"] = df["Type_VHL"]
        if "type_vhl" not in df.columns and "Type_VHL" not in df.columns:
            df["type_vhl"] = df["id"].map({e["id"]: e.get("type") for e in st.session_state.engins}).fillna("UNKNOWN")

        for e in st.session_state.engins:
            df.loc[df["id"] == e["id"], "cs"] = e["cs"]
            if e["cs"] in secteurs_initiaux:
                df.loc[df["id"] == e["id"], "x"] = secteurs_initiaux[e["cs"]].x
                df.loc[df["id"] == e["id"], "y"] = secteurs_initiaux[e["cs"]].y

        try:
            max_id = int(df["id"].max())
        except Exception:
            max_id = 0
        new_id = max_id + 1
        cs_coord = secteurs_initiaux[choix_cs]
        new_row = {
            "id": new_id,
            "cs": choix_cs,
            "x": cs_coord.x,
            "y": cs_coord.y,
            "type_vhl": add_type,
        }
        try:
            new_row["geometry"] = gpd.points_from_xy([new_row["x"]], [new_row["y"]])[0]
        except Exception:
            pass

        df = df.append(new_row, ignore_index=True)
        try:
            df = gpd.GeoDataFrame(df, geometry="geometry")
        except Exception:
            if "geometry" not in df.columns:
                df["geometry"] = gpd.points_from_xy(df["x"], df["y"]).values
            df = gpd.GeoDataFrame(df, geometry="geometry")

        try:
            interventions = get_interventions()
            sim_start = st.session_state.get("simulation_start")
            sim_end = st.session_state.get("simulation_end")
            if sim_start or sim_end:
                interventions = [i for i in interventions if (sim_start is None or i.date >= sim_start) and (sim_end is None or i.date <= sim_end)]
        except Exception as e:
            st.error(f"Impossible de charger les interventions: {e}")
            interventions = []

        with st.spinner("Optimisation en cours (petite fenêtre pour test)..."):
            try:
                df_final = opt.run_simulation(interventions, secteurs_initiaux, df, window_size=200, step=200)
            except Exception as e:
                st.error(f"Erreur optimisation: {e}")
                df_final = None

        if df_final is not None:
            inter_sim = opt.simuler_window_df_engins(interventions, secteurs_initiaux, df_final, start_idx=0, window_size=200)
            metrics = opt.eval_window(inter_sim, secteurs_initiaux)
            st.write("**Scores globaux**")
            st.json(metrics["global"]) 
            st.write("**Metrics par CS (extrait)**")
            cs_df = pd.DataFrame.from_dict(metrics["cs"], orient="index")
            st.dataframe(cs_df.head(10))
            map_opt = folium.Map(location=[48.8566, 2.3522], zoom_start=9)
            for _, r in df_final.iterrows():
                folium.CircleMarker(location=[r["y"], r["x"]], radius=6, popup=f"{r['id']}:{r.get('type_vhl','')}", color="blue", fill=True).add_to(map_opt)
            st.subheader("Positions finales des engins après optimisation")
            st_folium(map_opt, width=700, height=400)

# -----------------------------
# STAT CARD / INFO
# -----------------------------
if st.session_state.progress == 0:
    st.info("Simulation non terminée")
else:
    st.success("Simulation terminée")

# -----------------------------
# CARTE STATISTIQUE
# -----------------------------
stat_map = folium.Map(location=[48.8566, 2.3522], zoom_start=9)

if st.session_state.progress == 1:
    from main import interventions_simulees

    def get_stat(cs):
        interventions_cs = [i for i in interventions_simulees if i.cstc == cs]
        if len(interventions_cs) == 0:
            return datetime.timedelta(0)
        total = sum([i.trajet for i in interventions_cs], start=datetime.timedelta(0))
        return total / len(interventions_cs)

    temps = gdf["nom"].map(get_stat)
    temps_min = temps.min()
    temps_max = temps.max()

    def style_stat(f):
        cs = f["properties"]["nom"]
        t = get_stat(cs).total_seconds()
        min_sec = temps_min.total_seconds()
        max_sec = temps_max.total_seconds()
        ratio = 0 if max_sec == min_sec else (t - min_sec) / (max_sec - min_sec)
        r = int(255 * ratio)
        g = int(255 * (1 - ratio))
        b = 0
        return {
            "fillColor": f"#{r:02X}{g:02X}{b:02X}",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.6
        }

    folium.GeoJson(
        gdf,
        style_function=style_stat,
        tooltip=folium.GeoJsonTooltip(fields=["nom"], aliases=["Secteur"])
    ).add_to(stat_map)

st.subheader("Carte des performances par secteur")
st_folium(stat_map, width=700, height=500)
