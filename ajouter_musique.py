"""
Ajoute rapidement une ligne à musiques.csv à partir d'un lien YouTube,
sans avoir à extraire l'ID à la main.

Usage :
    python ajouter_musique.py "Hollow Knight" "https://youtu.be/xxxxxxxxxxx?t=45"

Astuce : sur YouTube, avance la vidéo jusqu'au passage que tu veux utiliser,
puis clic droit sur la vidéo -> "Copier l'URL de la vidéo à l'horodatage
actuel". Le lien copié contient déjà le timestamp, ce script le récupère
automatiquement (inutile de préciser --timestamp dans ce cas).

Ensuite, comme d'habitude, relance `python import_csv.py` pour intégrer les
nouvelles lignes à la base.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent / "musiques.csv"


def extraire_secondes(valeur: str) -> int:
    """Convertit '1m30s', '90s', '90' ou '1h2m3s' en nombre de secondes."""
    if valeur.isdigit():
        return int(valeur)
    total = 0
    for nombre, unite in re.findall(r"(\d+)([hms])", valeur):
        nombre = int(nombre)
        if unite == "h":
            total += nombre * 3600
        elif unite == "m":
            total += nombre * 60
        elif unite == "s":
            total += nombre
    return total


def extraire_id_et_timestamp(url: str) -> tuple[str, int]:
    """Accepte un lien YouTube sous à peu près n'importe quelle forme
    (youtube.com/watch?v=ID, youtu.be/ID, embed/ID, avec ou sans ?t=...)
    et en extrait l'ID de la vidéo + un timestamp de départ si présent."""
    match_id = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
    if not match_id:
        raise ValueError(f"Aucun ID de vidéo YouTube trouvé dans : {url}")
    youtube_id = match_id.group(1)

    timestamp = 0
    match_t = re.search(r"[?&](?:t|start)=([0-9hms]+)", url)
    if match_t:
        timestamp = extraire_secondes(match_t.group(1))

    return youtube_id, timestamp


def ajouter_musique(titre: str, url: str, timestamp_force: int | None = None) -> None:
    youtube_id, timestamp_detecte = extraire_id_et_timestamp(url)
    timestamp = timestamp_force if timestamp_force is not None else timestamp_detecte

    fichier_existe = CSV_PATH.exists()

    # Si le fichier existe déjà mais ne se termine pas par un retour à la
    # ligne, un ajout brut se collerait à la fin de la dernière ligne et
    # corromprait le CSV (ex: "...KBP1zYwBzOE,20Chrono Trigger,..."). On
    # s'assure donc qu'il y a bien un saut de ligne avant d'écrire.
    if fichier_existe:
        contenu = CSV_PATH.read_bytes()
        if contenu and not contenu.endswith((b"\n", b"\r")):
            with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
                f.write("\n")

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not fichier_existe:
            writer.writerow(["titre_jeu", "youtube_id", "timestamp_debut"])
        writer.writerow([titre, youtube_id, timestamp])

    print(f"Ajouté à musiques.csv : {titre}  (id={youtube_id}, départ à {timestamp}s)")
    print("   Relance `python import_csv.py` pour l'intégrer à la base.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ajoute une musique à musiques.csv à partir d'un lien YouTube."
    )
    parser.add_argument("titre", help="Titre du jeu, ex: 'Hollow Knight'")
    parser.add_argument("url", help="Lien YouTube, avec ou sans horodatage")
    parser.add_argument(
        "--timestamp",
        type=int,
        default=None,
        help="Force un timestamp de départ en secondes (sinon détecté automatiquement dans le lien)",
    )
    args = parser.parse_args()
    ajouter_musique(args.titre, args.url, args.timestamp)