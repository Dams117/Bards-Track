from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# 1. Configuration de la connexion SQLite
# Le fichier s'appellera "vgm_blindtest.db" et sera créé dans ton dossier actuel
SQLALCHEMY_DATABASE_URL = "sqlite:///./vgm_blindtest.db"

# check_same_thread=False est une spécificité requise par SQLite et FastAPI
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base est la classe mère dont vont hériter toutes nos tables
Base = declarative_base()

# --- 2. DÉFINITION DES TABLES (Modèles) ---

class Jeu(Base):
    __tablename__ = "jeux"
    
    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String, unique=True, index=True) # unique=True empêche les doublons
    
    # On crée un lien virtuel pour récupérer facilement les pistes d'un jeu
    pistes = relationship("Piste", back_populates="jeu")

class Piste(Base):
    __tablename__ = "pistes"
    
    id = Column(Integer, primary_key=True, index=True)
    jeu_id = Column(Integer, ForeignKey("jeux.id")) # Clé étrangère qui pointe vers la table jeux
    youtube_id = Column(String)
    timestamp_debut = Column(Integer)
    
    # Le lien inverse
    jeu = relationship("Jeu", back_populates="pistes")

class TirageDuJour(Base):
    """
    Verrouille, pour une date donnée, la piste qui a été tirée ce jour-là.

    Sans cette table, l'index du jour était recalculé à chaque requête à
    partir du nombre total de pistes en base à cet instant précis. Si tu
    importais de nouvelles musiques (import_csv.py) pendant qu'une partie
    était en cours, ce total changeait, et /verifier-reponse pouvait alors
    comparer la réponse du joueur à une musique différente de celle qu'il
    venait d'écouter via /musique-du-jour. Avec cette table, le premier
    appel de la journée fige le résultat, et tous les suivants réutilisent
    la même piste jusqu'au lendemain.
    """
    __tablename__ = "tirages_du_jour"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True, index=True)  # format "AAAA-MM-JJ"
    piste_id = Column(Integer, ForeignKey("pistes.id"))

    piste = relationship("Piste")

# --- 3. CRÉATION PHYSIQUE DE LA BASE ---
# Cette ligne vérifie si le fichier .db existe, et crée les tables à l'intérieur s'il est vide
Base.metadata.create_all(bind=engine)