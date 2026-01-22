from datetime import timedelta
import time
import pandas as pd
import marimo as mo

from utils.graph_utils import inter_nodes


class Simulation:
    def __init__(self, df: pd.DataFrame, engins_courants, G):
        self.df = df
        self.en_cours = df[0:0].copy()
        self.engins_courants = engins_courants
        self.stats_engins = pd.DataFrame(
            columns=["id", "disponible", "iteration"]
        )
        self.stats_engins_final = self.stats_engins[0:0].copy()
        self.G = G

    def maj_indisponibilite_temp(self, curseur):
        # TODO Améliorer complexité d'indispo grace à indispo_temp dans les calculs de la boucle
        if curseur.hour == 23 or curseur.hour < 8:
            self.engins_courants.loc[
                (self.engins_courants["Type_VHL"] == "VSAV")
                & (self.engins_courants["Regime"] == "Modulaire")
                & (self.engins_courants["cs"] != "VILC"),
                "indisponibilite_temp",
            ] = 1
        else:
            self.engins_courants["indisponibilite_temp"] = 0
            self.engins_courants.loc[
                self.engins_courants.index.isin(
                    self.engins_courants[
                        (self.engins_courants["modularite"] > 0)
                        & (self.engins_courants["Type_VHL"] == "PSE")
                        & (self.engins_courants["disponible"] == 1)
                    ]["modularite"]
                ),
                "disponible",
            ] = 1
        self.engins_courants.loc[
            self.engins_courants["indisponibilite_temp"] == 1, "disponible"
        ] = 0

    def remettre_disponibles(self,df_release): 
        self.engins_courants.loc[self.engins_courants.index.isin(df_release["engin"]), "disponible"] = 1
        df_release = df_release[df_release["modularite"] > 0]
        for _, i in df_release.iterrows():
            elem = self.engins_courants.loc[i["engin"]]
            if elem["Type_VHL"] == "PSE":
                dispo_mod = self.engins_courants.loc[self.engins_courants["modularite"] == i["modularite"], "disponible"].iloc[0]
                self.engins_courants.loc[i["engin"], "Interventions"] = ("POMPE" if dispo_mod == 1 else "VSAV") 
            else:
                dispo_mod = self.engins_courants.loc[i["modularite"], "disponible"] 
                if dispo_mod == 1:
                    self.engins_courants.loc[i["modularite"], "Interventions"] = "POMPE" 

    def traiter_interventions(self, df_curr):
        couts, liste_engins, modularitees = [], [], []
        for _, x in df_curr.iterrows():
            e, m, t = inter_nodes(
                x,
                self.engins_courants[
                    (self.engins_courants["Interventions"] == x["fem_mma"])
                    & (self.engins_courants["disponible"] == 1)
                ],
                self.G,
            )
            couts.append(
                pd.to_datetime(x["selection"])
                + timedelta(minutes=round(x["traitement"] / 60, 0))
                + timedelta(minutes=round(t / 60, 0))
            )
            liste_engins.append(e)
            modularitees.append(m)
            self.engins_courants.loc[
                self.engins_courants.index == e, "disponible"
            ] = 0
            if m != 0:
                if x["fem_mma"] == "VSAV":
                    self.engins_courants.loc[
                        self.engins_courants["modularite"] == e,
                        "Interventions",
                    ] = "VSAV"
                else:
                    self.engins_courants.loc[
                        self.engins_courants["modularite"] == e, "disponible"
                    ] = 0

        df_curr["selection"] = couts
        df_curr["engin"] = liste_engins
        df_curr["modularite"] = modularitees
        return df_curr

    def loop_opti(
        self,
        df: pd.DataFrame,
        start: str,
        end: str,
        en_cours_batch,
    ):
        duration = time.time()
        duration_logs = 0
        duration_indispo = 0
        duration_selection = 0
        duration_release = 0
        duration_filter_inter = 0
        duration_filter_inter_end = 0
        for curseur in mo.status.progress_bar(
            pd.Series(
                pd.date_range(
                    start=start, end=end, freq="min", inclusive="left"
                )
            ),
            title="Chargement",
            subtitle="Veuillez pantienter",
            show_eta=True,
            show_rate=True,
            remove_on_exit=True,
            disabled=True,
        ):
            duration_epoch = time.time()
            self.maj_indisponibilite_temp(curseur)
            duration_indispo += time.time() - duration_epoch

            duration_epoch = time.time()
            df_curr = df[
                (df["selection"] == curseur) & (df["next"] == "inter")
            ].copy()
            duration_filter_inter += time.time() - duration_epoch

            duration_epoch = time.time()
            df_release = en_cours_batch[
                (en_cours_batch["selection"] == curseur)
                & (en_cours_batch["next"] == "dispo")
            ].copy()
            duration_filter_inter_end += time.time() - duration_epoch

            duration_epoch = time.time()
            if not df_curr.empty:
                df_curr["next"] = "dispo"
                df_curr = self.traiter_interventions(df_curr)
                en_cours_batch = pd.concat((df_curr, en_cours_batch))
            duration_selection += time.time() - duration_epoch

            duration_epoch = time.time()
            if not df_release.empty:
                self.remettre_disponibles(df_release)
            duration_release += time.time() - duration_epoch

            if curseur.minute % 10 == 0:
                duration_epoch = time.time()
                self.engins_courants["iteration"] = curseur
                self.stats_engins = pd.concat(
                    [
                        self.stats_engins,
                        self.engins_courants.reset_index()[
                            ["id", "disponible", "iteration"]
                        ],
                    ]
                )
                duration_logs += time.time() - duration_epoch

        # Logging globalement Sélection des engins = ~50% du temps de calcul
        print(f"==============================")
        print(f'Itération : {start}')
        print(f"Durée: {time.time() - duration}")
        print(f"Filtrage des interventions epoch: {duration_filter_inter}")
        print(f"Filtrage des interventions à cloturer: {duration_filter_inter_end}")
        print(f"Sauvegarde engins: {duration_logs}")
        print(f"Indisponibilité temporaire (PSE): {duration_indispo}")
        print(f"Sélection des engins: {duration_selection}")
        print(f"Libération des engins: {duration_release}")

        # Interventions en cours, historique dispos engins, listing des engins dispos
        self.en_cours = pd.concat(
            [
                self.en_cours[
                    ~self.en_cours["engagement"].isin(
                        en_cours_batch["engagement"]
                    )
                ],
                en_cours_batch,
            ]
        )
        self.stats_engins_final = pd.concat(
            [self.stats_engins, self.stats_engins_final]
        )
        self.stats_engins = self.stats_engins.astype("object")[0:0]

    def run(self, start, end, opti_pas: str = "1D"):
        batches = pd.Series(
            pd.date_range(
                start=start, end=end, freq=opti_pas, inclusive="left"
            )
        )
        mo.output.append(
            mo.md(f"""<div style="text-align: center;">
                            <h3>Simulation lancée, du {start} au {end}</h3>
                            </div>""")
        )
        with mo.status.progress_bar(
            title="Chargement",
            subtitle="Veuillez patienter",
            show_eta=True,
            show_rate=True,
            total=len(batches),
        ) as semaines:
            for batch_i in range(len(batches)):
                batch_start = batches.get(batch_i)
                batch_end = batches.get(batch_i + 1, end)

                df_batch = self.df[
                    (self.df["selection"] > batch_start)
                    & (self.df["selection"] < batch_end)
                ].copy()

                en_cours_batch = self.en_cours[
                    self.en_cours["selection"] > batch_start
                ]

                self.loop_opti(
                    df_batch,
                    batch_start,
                    batch_end,
                    en_cours_batch,
                )
                semaines.update_progress()

        return self.en_cours, self.stats_engins_final