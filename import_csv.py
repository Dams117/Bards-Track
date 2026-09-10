import csv
from database import SessionLocal, Jeu, Piste

def importer_depuis_csv(nom_fichier):
    db = SessionLocal()
    
    print(f"📂 Ouverture du fichier {nom_fichier}...")
    
    try:
        # On ouvre le fichier CSV en mode lecture ('r')
        with open(nom_fichier, mode='r', encoding='utf-8') as fichier:
            # DictReader transforme chaque ligne en dictionnaire pour lire facilement les colonnes
            lecteur_csv = csv.DictReader(fichier)
            
            compteur = 0
            
            # On boucle sur chaque ligne du tableau
            for ligne in lecteur_csv:
                titre = ligne['titre_jeu'].strip()
                yt_id = ligne['youtube_id'].strip()
                timestamp = int(ligne['timestamp_debut'])
                
                # 1. On vérifie si ce jeu existe déjà dans la base de données
                jeu_existant = db.query(Jeu).filter(Jeu.titre == titre).first()
                
                # Si le jeu n'existe pas, on le crée
                if not jeu_existant:
                    nouveau_jeu = Jeu(titre=titre)
                    db.add(nouveau_jeu)
                    db.commit() # On sauvegarde pour que SQLite lui donne un ID
                    jeu_existant = nouveau_jeu
                    print(f"🎮 Nouveau jeu ajouté : {titre}")
                
                # 2. On vérifie si CETTE piste spécifique existe déjà pour ce jeu
                piste_existante = db.query(Piste).filter(
                    Piste.youtube_id == yt_id,
                    Piste.jeu_id == jeu_existant.id
                ).first()
                
                # Si la piste n'existe pas, on l'ajoute
                if not piste_existante:
                    nouvelle_piste = Piste(
                        jeu_id=jeu_existant.id,
                        youtube_id=yt_id,
                        timestamp_debut=timestamp
                    )
                    db.add(nouvelle_piste)
                    compteur += 1
                    print(f"🎵 Nouvelle piste ajoutée pour {titre} (ID: {yt_id})")
            
            # On valide tous les ajouts finaux
            db.commit()
            print(f"✅ Importation terminée ! {compteur} nouvelles pistes ajoutées.")

    except FileNotFoundError:
        print(f"❌ Erreur : Le fichier {nom_fichier} est introuvable.")
    except Exception as e:
        print(f"❌ Une erreur s'est produite : {e}")
    finally:
        db.close()

# Lancement du script
if __name__ == "__main__":
    importer_depuis_csv("musiques.csv")