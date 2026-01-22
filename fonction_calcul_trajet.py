import numpy as np
import pandas as pd
import joblib

df_temps_caserne_inter = pd.read_csv("df_total_brute.csv")

modele = joblib.load("adaptative_weight.pkl")
model_low= joblib.load("adaptative_weight_low_value_400.pkl")
PRECISION = 5
def float_key(f, precision=PRECISION):
    return int(round(f * 10**precision))
df_dict = {
    (float_key(row.x_vhl), float_key(row.y_vhl), float_key(row.x_inter), float_key(row.y_inter)): row.temps
    for row in df_temps_caserne_inter.itertuples(index=False)
}
    
def encodage_temporel(date):
    # Encodage temporel
    date = pd.to_datetime(date)
    heure = date.hour + date.minute / 60.0
    theta = 2 * np.pi * heure / 24
    sin_heure = np.sin(theta)
    cos_heure = np.cos(theta)

    jour = date.dayofweek
    week_end = 1 if jour >= 5 else 0

    return sin_heure, cos_heure, week_end
    
def infer_lgbm(x_vhl, y_vhl, x_inter, y_inter, date, tmax=350):
    key = (
        float_key(x_vhl),
        float_key(y_vhl),
        float_key(x_inter),
        float_key(y_inter)
    )

    # accès rapide sans KeyError
    temps = df_dict.get(key)
    if temps is not None:
        return float(temps)  # déjà existant
    else:
        # si clé non trouvée, utiliser le modèle
        sin_heure, cos_heure, week_end = encodage_temporel(date)

        X = pd.DataFrame([{
            "x_inter": x_inter,
            "y_inter": y_inter,
            "x_vhl": x_vhl,
            "y_vhl": y_vhl,
            "sin_heure": sin_heure,
            "cos_heure": cos_heure,
            "week_end": week_end
        }])

        pred_main = np.maximum(modele.predict(X)[0], 0)
        pred_final = (
            np.maximum(model_low.predict(X)[0], 0)
            if pred_main < tmax else pred_main
        )

        return float(pred_final)
        
def sample_df_for_knn(df, frac=0.1, segment_col=None, random_state=42):
    """
    Renvoie une fraction de la DataFrame pour construire un KNN rapide.

    Args:
        df (pd.DataFrame): dataframe complète
        frac (float): fraction à prendre (0 < frac <= 1)
        segment_col (str or None): si spécifié, échantillonne **par segment**
        random_state (int): pour reproductibilité

    Returns:
        pd.DataFrame: sous-échantillon de df
    """
    if segment_col is None:
        return df.sample(frac=frac, random_state=random_state)
    else:
        # Échantillonnage stratifié par segment
        return df.groupby(segment_col, group_keys=False).apply(
            lambda x: x.sample(frac=frac, random_state=random_state)
        )
        
df_sampled = sample_df_for_knn(df_temps_caserne_inter, frac=0.1)

# 2) Construction de l'espace KNN
X_sample = np.column_stack([
    df_sampled['x_vhl'].values,
    df_sampled['y_vhl'].values,
    0.3 * df_sampled['x_inter'].values,
    0.3 * df_sampled['y_inter'].values
])                           #  Le 0.3 suffit pour que la comparaison soit entre les cs puis entre les inters        

y_sample = df_sampled['temps'].values

# 3) Entraînement du KDTree
knn_model = NearestNeighbors(
    n_neighbors=3,
    algorithm="kd_tree"
).fit(X_sample)

def knn(
    x_vhl, y_vhl,
    x_inter, y_inter,
    knn_model,
    y_sample,
    alpha=0.3
):
    """
    Approxime le temps de trajet via KNN pondéré VHL > INTER.
    """
    X_query = np.array([[
        x_vhl,
        y_vhl,
        alpha * x_inter,
        alpha * y_inter
    ]])

    distances, indices = knn_model.kneighbors(X_query)

    # moyenne des k voisins
    temps_pred = y_sample[indices[0]].mean()
    return temps_pred

def infer(x_vhl, y_vhl, x_inter, y_inter, date, tmax=350):
    key = (
        float_key(x_vhl),
        float_key(y_vhl),
        float_key(x_inter),
        float_key(y_inter)
    )

    # accès rapide sans KeyError
    temps = df_dict.get(key)
    if temps is not None:
        return float(temps)  # déjà existant
    else:
        pred_knn = knn(
            x_vhl, y_vhl,
            x_inter, y_inter,
            knn_model,
            y_sample,
            alpha=0.3
        )
        return float(pred_knn)

