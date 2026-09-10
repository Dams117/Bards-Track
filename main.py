import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, Jeu, Piste, TirageDuJour
from import_csv import importer_depuis_csv
from fastapi.middleware.cors import CORSMiddleware

# Dossier du projet, pour que les chemins marchent quel que soit l'endroit
# d'où la commande de démarrage est lancée (important une fois déployé).
DOSSIER_PROJET = Path(__file__).resolve().parent
DOSSIER_STATIC = DOSSIER_PROJET / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On (ré)importe le CSV à chaque démarrage du serveur. C'est sans danger
    # (import_csv.py ignore les doublons), et ça veut dire que le catalogue
    # se reconstitue tout seul même sur un hébergeur au disque éphémère
    # (ex. Render en free tier), où le fichier .db repart de zéro à chaque
    # redémarrage : musiques.csv, lui, reste dans le dépôt Git.
    importer_depuis_csv(str(DOSSIER_PROJET / "musiques.csv"))
    yield


app = FastAPI(title="VGM Blind Test API", lifespan=lifespan)

# --- AUTORISATION CORS ---
# Le front est maintenant servi par cette même app (voir le mount plus bas),
# donc ce middleware n'est plus indispensable en usage normal. On le laisse
# pour le cas où tu ouvres le front depuis une autre origine en dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Date de lancement du jeu : sert à numéroter les jours ("Blind Test n°1, n°2...")
DATE_DEBUT = date(2026, 9, 8)

# Tolérance aux fautes de frappe/accents sur la réponse (0 à 1, 1 = exact uniquement).
# Volontairement élevé : on veut pardonner un accent ou une lettre manquante sur un
# titre long, mais pas confondre "Halo 3" et "Halo 4".
SEUIL_SIMILARITE = 0.90


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PropositionJoueur(BaseModel):
    proposition: str


# --- NORMALISATION ET COMPARAISON DES RÉPONSES ---

def normaliser(texte: str) -> str:
    """minuscules, sans accents, sans ponctuation, espaces multiples compactés."""
    texte = texte.strip().lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(caractere for caractere in texte if unicodedata.category(caractere) != "Mn")
    texte = re.sub(r"[^a-z0-9\s]", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def reponses_equivalentes(proposition: str, vrai_titre: str) -> bool:
    a, b = normaliser(proposition), normaliser(vrai_titre)
    if a == b:
        return True
    # Filet de sécurité pour une petite faute de frappe sur un titre long,
    # sans devenir assez permissif pour valider un mauvais numéro d'épisode.
    return SequenceMatcher(None, a, b).ratio() >= SEUIL_SIMILARITE


# --- L'ALGORITHME DU JOUR ---

def numero_du_jour() -> int:
    return (date.today() - DATE_DEBUT).days + 1


def obtenir_piste_du_jour(db: Session):
    aujourdhui = date.today().isoformat()

    # Si la piste du jour a déjà été tirée plus tôt aujourd'hui, on la
    # réutilise telle quelle : ça garantit que la musique écoutée et la
    # musique vérifiée sont toujours les mêmes, même si le catalogue
    # change en cours de journée (import d'un nouveau CSV, etc.).
    tirage_existant = db.query(TirageDuJour).filter(TirageDuJour.date == aujourdhui).first()
    if tirage_existant:
        return tirage_existant.piste

    toutes_les_pistes = db.query(Piste).order_by(Piste.id).all()

    if not toutes_les_pistes:
        return None

    total_pistes = len(toutes_les_pistes)
    jours_ecoules = (date.today() - DATE_DEBUT).days
    index_du_jour = jours_ecoules % total_pistes

    piste_choisie = toutes_les_pistes[index_du_jour]

    db.add(TirageDuJour(date=aujourdhui, piste_id=piste_choisie.id))
    db.commit()

    return piste_choisie


@app.get("/statut")
def statut():
    return {"statut": "en ligne", "message": "L'API connectée à SQLite est prête !"}


@app.get("/musique-du-jour")
def get_musique(db: Session = Depends(get_db)):
    piste_du_jour = obtenir_piste_du_jour(db)

    if piste_du_jour is None:
        raise HTTPException(status_code=404, detail="Aucune musique dans le catalogue pour l'instant.")

    return {
        "id_piste": piste_du_jour.id,
        "youtube_id": piste_du_jour.youtube_id,
        "timestamp_debut": piste_du_jour.timestamp_debut,
        "numero_jour": numero_du_jour(),
    }


@app.get("/liste-jeux")
def get_liste_jeux(db: Session = Depends(get_db)):
    jeux = db.query(Jeu).all()
    titres = [jeu.titre for jeu in jeux]
    return sorted(titres)


@app.post("/verifier-reponse")
def verifier_reponse(donnees: PropositionJoueur, db: Session = Depends(get_db)):
    piste_du_jour = obtenir_piste_du_jour(db)

    if piste_du_jour is None:
        raise HTTPException(status_code=404, detail="Aucune musique dans le catalogue pour l'instant.")

    vrai_jeu = db.query(Jeu).filter(Jeu.id == piste_du_jour.jeu_id).first()

    if reponses_equivalentes(donnees.proposition, vrai_jeu.titre):
        return {"victoire": True, "message": "Eh beh voila tu vois quand tu veux !"}
    else:
        return {"victoire": False, "message": "Bah non c'est pas ça l'idiot du village réessaie !"}


# --- LE SITE STATIQUE ---
# Monté en dernier et sur "/", pour que les routes API ci-dessus gardent la
# priorité. Tout le reste (/, /style.css, /script.js...) tombe sur les
# fichiers dans static/. C'est ça qui permet d'avoir un seul service à
# déployer, sans souci de CORS ni d'URL à changer entre local et prod.
app.mount("/", StaticFiles(directory=DOSSIER_STATIC, html=True), name="frontend")