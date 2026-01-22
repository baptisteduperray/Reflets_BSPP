from dotenv import load_dotenv
import os

load_dotenv()

INTERVENTIONS = os.getenv("INTERVENTIONS")
RED = os.getenv("RED")
LIEN_RED_INTER = os.getenv("LIEN_RED_INTER")
RESEAU = os.getenv("RESEAU")
LSO = os.getenv("LSO")
ENGINS = os.getenv("ENGINS")
CARTE_BSPP = os.getenv("CARTE_BSPP")
SQLALCHEMY_DATABASE_INFOCENTRE = os.getenv("SQLALCHEMY_DATABASE_INFOCENTRE")
SQLALCHEMY_DATABASE_INFOREF = os.getenv("SQLALCHEMY_DATABASE_INFOREF")