from typing import Dict, Tuple, List
import datetime
import geopandas as gpd
from fonction_calcul_trajet import infer as calcul_trajet
from abc import ABC, abstractmethod

POMPE, PSE, VSAV = "POMPE", "PSE", "VSAV"
global compteur
compteur = 0

class Secteur:
    df: gpd.GeoDataFrame

    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y


class Intervention:
    df: gpd.GeoDataFrame

    def __init__(self,proc, id, x: float, y: float, date: datetime.datetime, traitement: datetime.timedelta,
                 trajet: datetime.timedelta, fem_mma: str, cstc: str, ) -> None:
        self.x = x
        self.y = y
        self.date = date
        self.traitement = traitement
        self.trajet = trajet
        self.fem_mma = fem_mma
        self.cstc = cstc
        self.id = id
        self.proc = proc

    @property
    def duree_sur_place(self):
        # Variables calculees
        return self.traitement - self.trajet

class Engin(ABC):
    df: gpd.GeoDataFrame

    def __init__(self, _id, cs, x_cs, y_cs) -> None:

        ## Données


        # Les _ indiquent variables privées (notation)
        self.id: float = _id
        self.x_cs: float = x_cs
        self.y_cs: float = y_cs
        self.cs: str = cs

        self.modularite = None

        ## Fonctionnement
        self._en_caserne: datetime.datetime = datetime.datetime.min # Date à partir de laquelle il est à la caserne
        self._plus_en_inter: datetime.datetime = datetime.datetime.min # Date à partir de laquelle il a fini son intervention
        # Normalement, self._en_caserne > self._en_inter

        self._intervention: Intervention | None = None
        self.temps_de_sorties_de_la_caserne: List[datetime.datetime] = []
        self.temps_de_retour_a_la_caserne: List[datetime.datetime] = []

        ## Variables pour économiser du temps de calcul
        self.X = 0
        self.Y = 0
        self.DEPART_DEPUIS_CASERNE = 1
        self.x_enregistres: Dict[datetime.datetime, Tuple[float, bool]] = {}
        self.y_enregistres: Dict[datetime.datetime, Tuple[float, bool]] = {}

    def is_in_caserne(self, date) -> bool:
        """
        Retourne vrai ssi l'engin est dans sa caserne
        :param date:
        :return:
        """
        return date >= self._en_caserne

    def nombre_de_sorties(self):
        assert len(self.temps_de_sorties_de_la_caserne) == len(self.temps_de_retour_a_la_caserne)
        return len(self.temps_de_sorties_de_la_caserne)

    def derniere_intervention(self) -> Intervention:
        return self._intervention

    def est_disponible(self, intervention: Intervention) -> bool:
        date = intervention.date
        # TODO: FAUT PAS OUBLIER D'ENLEVER _intervention s'il n'est pas disponible
        b = self._plus_en_inter <= date
        """if b:
            self._intervention = None"""
        return b

    def distance_euclidienne_au_carre(self, intervention: Intervention) -> float:
        """
        Renvoie la distance euclienne au carré (evite de faire la racine)
        """
        date = intervention.date
        x, y = intervention.x, intervention.y
        if not self.est_disponible(intervention):
            print("Attention on appelle distance_euclidienne au carre alors que l'engin n'est pas disponible")

        return (self.x(date)[self.X] - x) ** 2 + (self.y(date)[self.Y] - y) ** 2

    @abstractmethod
    def set_modularite(self, engin) -> None:
        ...

    def x(self, date) -> Tuple[float, bool]: # x, depart_depuis_caserne?
        if date in self.x_enregistres:
            return self.x_enregistres[date]

        if date >= self._en_caserne: # S'il est à la caserne
            return self.x_cs, True
        
        if date <= self._plus_en_inter:
            assert self._intervention != None
            return self._intervention.x, False

        # self._pas_en_inter <= date <= self._en_caserne
        # il est en train de rentrer

        pourcentage = (date - self._plus_en_inter) / (self._en_caserne - self._plus_en_inter)

        assert self._intervention != None

        x_estimated = (1-pourcentage)*self._intervention.x + pourcentage*self.x_cs

        self.x_enregistres[date] = x_estimated, False
        return x_estimated, False # Il part pas depuis sa caserne
    
    def y(self, date) -> Tuple[float, bool]:
        if date in self.y_enregistres:
            return self.y_enregistres[date]

        if date >= self._en_caserne: # S'il est à la caserne
            return self.y_cs, True
        
        if date <= self._plus_en_inter:
            assert self._intervention != None
            return self._intervention.y, False

        # self._pas_en_inter <= date <= self._en_caserne
        # il est en train de rentrer

        pourcentage = (date - self._plus_en_inter) / (self._en_caserne - self._plus_en_inter)

        assert self._intervention != None

        y_estimated = (1-pourcentage)*self._intervention.y + pourcentage*self.y_cs

        self.y_enregistres[date] = y_estimated, False
        return y_estimated, False

    def temps_trajet(self, intervention:Intervention) -> Tuple[datetime.timedelta, float, float, bool]:
        # On récupère la position de l'engin au moment où il se fait appeler pour aller en intervention
        x_vhl, depart_depuis_caserne = self.x(intervention.date)
        y_vhl, _ = self.y(intervention.date)

        return datetime.timedelta(seconds=calcul_trajet(x_vhl, y_vhl, intervention.x, intervention.y, intervention.date)), x_vhl, y_vhl, depart_depuis_caserne

    def attribuer_a(self, intervention: Intervention) -> Tuple[datetime.timedelta, float, float, bool]:
        # TODO passer un PSE en VSAV quand son pair part.

        self._intervention = intervention
        temps_trajet, x_vhl, y_vhl, depart_depuis_caserne = self.temps_trajet(intervention) # On récupère la position de l'engin au momement où il se fait appeler pour aller en intervention

        ### Premier bout de logique pour prendre les stats de l'engin
        remplacer = False
        if self._en_caserne <= intervention.date:
            self.temps_de_sorties_de_la_caserne.append(intervention.date)
        elif self._plus_en_inter <= intervention.date <= self._en_caserne:
            remplacer = True
        else:
            raise ValueError("L'intervention qu'on essaie d'attribuer a lieu avant que l'engin ne finisse sont intervention precedente")
        ### ================================================

        self._plus_en_inter = intervention.date + temps_trajet + intervention.duree_sur_place
        self._en_caserne = intervention.date + 2*temps_trajet + intervention.duree_sur_place

        # Deuxieme bout
        if remplacer:
            self.temps_de_retour_a_la_caserne[-1] = self._en_caserne
        else:
            self.temps_de_retour_a_la_caserne.append(self._en_caserne)
        # -===================

        return temps_trajet, x_vhl, y_vhl, depart_depuis_caserne

class POMPE_Engin(Engin):
    def __init__(self, _id, cs, x_cs, y_cs) -> None:
        super().__init__(_id, cs, x_cs, y_cs)

    def __repr__(self) -> str:
        return "POMPE(id={}, cs={})".format(self.id, self.cs)

    def set_modularite(self, engin: None | Engin) -> None:
        assert engin is None

class VSAV_Engin(Engin):

    def __init__(self, _id, cs, x_cs, y_cs) -> None:
        super().__init__(_id, cs, x_cs, y_cs)

    def __repr__(self) -> str:
        return "VSAV(id={}, cs={})".format(self.id, self.cs)

    def set_modularite(self, engin: None | Engin) -> None:
        assert isinstance(engin, PSE_Engin)
        self.modularite = engin

    def est_disponible(self, intervention: Intervention) -> bool:
        date = intervention.date
        if not self.modularite: # si le VSAV est modulaire la variable contient son pair, sinon elle contient None
            return super().est_disponible(intervention)

        if date <= self._plus_en_inter:
            return False

        if plage_interdite_nuit(date): #Un véhicule VSAV couplé un PSE ne part jamais en intervention à ces heures-là
            return False

        # Là il faut voir si le PSE est en intervention:
        #   -> s il est a la caserne  on part
        #   -> s il est pas dans la caserne en tant que VSAV on part

        if self.modularite.is_in_caserne(date):
            # le PSE pair est a la caserne
            return True
        # il est pas a la caserne
        if self.modularite.is_VSAV(date):
            return True



class PSE_Engin(Engin):
    def __init__(self, _id, cs, x_cs, y_cs) -> None:
        super().__init__(_id, cs, x_cs, y_cs)

    def __repr__(self) -> str:
        return "PSE(id={}, cs={})".format(self.id, self.cs)

    def set_modularite(self, engin: None | Engin) -> None:
        assert isinstance(engin, VSAV_Engin)
        self.modularite = engin

    def is_VSAV(self, date) -> bool:
        if not self.is_in_caserne(date):
            return self.derniere_intervention().fem_mma == VSAV #Si jamais ca retourne un None cest parce quil faut revoir la facon dont on stocke les interventions, peut etre les passer a une liste ou creer une variable derniere intervention

        else:
            raise NotImplementedError("On pose cette question uniquement si le PSE n'est pas dans la caserne")

    def est_disponible(self, intervention: Intervention) -> bool:
        date = intervention.date
        fem_mma = intervention.fem_mma
        code_rouge = intervention.proc == 'R'
        if not self.modularite:
            return super().est_disponible(intervention)

        if date <= self._plus_en_inter:
            return False

        if fem_mma == POMPE:
            return self.modularite.is_in_caserne(date)

        if fem_mma == VSAV:
            if plage_interdite_nuit(date):
                return code_rouge
            else:
                return True




def plage_interdite_nuit(date: datetime.datetime) -> bool:
    LUNDI, JEUDI, VENDREDI, SAMEDI, DIMANCHE = 0, 3, 4, 5, 6
    heure, jour = date.time(), date.weekday()
    if LUNDI <= jour <= VENDREDI:
        if datetime.time(0, 0) <= heure <= datetime.time(8, 0):
            return True

    if jour == DIMANCHE or LUNDI <= jour <= JEUDI:
        if datetime.time(23, 0) <= heure <= datetime.time(0, 0):
            return True

    if SAMEDI <= jour <= DIMANCHE:
        if datetime.time(0, 0) <= heure <= datetime.time(7, 0):
            return True

    return False



class InterventionSimulee(Intervention):
    def __init__(self, engin: Engin, temps_trajet: datetime.timedelta, **kwargs) -> None:
        super().__init__(**kwargs)
        self.engin = engin
        self.trajet = temps_trajet

    @classmethod
    def from_Intervention(cls, intervention: Intervention, engin: Engin, temps_trajet: datetime.timedelta):
        return cls(engin, temps_trajet, **vars(intervention))
    
    def __repr__(self) -> str:
        return "InterventionSimulee(id={}, engin_id={}, type_engin={}, date={})".format(self.id, self.engin.id, self.engin.__class__.__name__, self.date)
