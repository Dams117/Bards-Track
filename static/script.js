// Vide car le site est maintenant servi par FastAPI lui-même : les appels
// vers "/musique-du-jour" etc. restent sur la même origine, en local comme
// une fois déployé. Plus besoin de CORS ni d'adresse à changer au déploiement.
const API_URL = "";
let player;
let musiqueDuJour = null;
let tentatives = 0;
const MAX_TENTATIVES = 5;
let partieTerminee = false;
let ytApiPrete = false; // Permet de savoir si le script Google est chargé

// --- 1. INITIALISATION DE LA PAGE ---
async function initialiserJeu() {
    try {
        // A. On va chercher la musique du jour
        const resMusique = await fetch(`${API_URL}/musique-du-jour`);
        if (!resMusique.ok) {
            throw new Error("Le serveur n'a pas de musique à proposer pour l'instant.");
        }
        musiqueDuJour = await resMusique.json();

        // A bis. On affiche le petit badge "Blind Test n°X"
        const badgeJour = document.getElementById("badge-jour");
        if (badgeJour && musiqueDuJour.numero_jour) {
            badgeJour.innerText = `Blind Test n°${musiqueDuJour.numero_jour}`;
        }

        // B. On regarde dans la mémoire du navigateur pour bloquer la triche au F5
        chargerSauvegarde();

        // C. On prévient le lecteur YouTube qu'on a reçu la musique
        essayerCreerLecteur();

    } catch (error) {
        document.getElementById("message-resultat").innerHTML = "❌ Impossible de se connecter à l'API.";
    }
}

// --- GESTION DE LA MÉMOIRE (LOCALSTORAGE) ---
function chargerSauvegarde() {
    const sauvegarde = JSON.parse(localStorage.getItem("vgm_blindtest_sauvegarde"));
    
    // Si on trouve une sauvegarde ET qu'elle correspond à la musique d'aujourd'hui
    if (sauvegarde && sauvegarde.id_piste === musiqueDuJour.id_piste) {
        tentatives = sauvegarde.tentatives;
        partieTerminee = sauvegarde.partieTerminee;
        
        document.getElementById("texte-compteur").innerText = `Essais : ${tentatives} / ${MAX_TENTATIVES}`;
        
        if (partieTerminee) {
            document.getElementById("input-jeu").disabled = true;
            document.getElementById("btn-valider").disabled = true;
            
            const messageDiv = document.getElementById("message-resultat");
            if (sauvegarde.victoire) {
                messageDiv.innerHTML = `<span style="color: #4CAF50;">T'as déjà trouvé mon pauvre casse toi et reviens demain !</span>`;
            } else {
                messageDiv.innerHTML = `<span style="color: #f44336;">Haha looser t'as perdu tu vas chialer ? Casse toi et reviens demain !</span>`;
            }
        }
    } else {
        // Nouveau jour : on vide la mémoire
        localStorage.removeItem("vgm_blindtest_sauvegarde");
    }
}

function sauvegarderProgression(victoire) {
    const etatActuel = {
        id_piste: musiqueDuJour.id_piste,
        tentatives: tentatives,
        partieTerminee: partieTerminee,
        victoire: victoire
    };
    localStorage.setItem("vgm_blindtest_sauvegarde", JSON.stringify(etatActuel));
}

// --- 2. GESTION DU LECTEUR YOUTUBE INVISIBLE ---
function onYouTubeIframeAPIReady() {
    ytApiPrete = true;
    essayerCreerLecteur();
}

// La fonction qui vérifie que tout est prêt avant de créer le lecteur
function essayerCreerLecteur() {
    if (ytApiPrete && musiqueDuJour && !player) {
        player = new YT.Player('lecteur-yt', {
            videoId: musiqueDuJour.youtube_id,
            playerVars: {
                'start': musiqueDuJour.timestamp_debut,
                'controls': 0,
                'disablekb': 1,
                'rel': 0
            },
            events: {
            'onReady': function(event) {
                const btnPlay = document.getElementById("btn-play");
                btnPlay.innerHTML = `<svg viewBox="0 0 24 24" width="32" height="32"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>`;
                btnPlay.disabled = false;
                
                // On affiche la durée totale dès que la vidéo est prête
                setTimeout(mettreAJourBarre, 500);
            },
            // NOUVEAU : On écoute si la musique est en lecture ou en pause
            'onStateChange': function(event) {
                if (event.data === YT.PlayerState.PLAYING) {
                    // Si ça joue, on actualise la barre rouge très rapidement (toutes les 100ms)
                    intervalProgression = setInterval(mettreAJourBarre, 100);
                } else {
                    // Si on fait pause, on arrête d'actualiser
                    clearInterval(intervalProgression);
                }
            }
        }
        });
    }
}

document.getElementById("btn-play").addEventListener("click", () => {
    if (player && typeof player.playVideo === "function") player.playVideo();
});

document.getElementById("btn-pause").addEventListener("click", () => {
    if (player && typeof player.pauseVideo === "function") player.pauseVideo();
});

// --- 3. VÉRIFICATION DE LA RÉPONSE ---
document.getElementById("btn-valider").addEventListener("click", async () => {
    if (partieTerminee) return;

    const input = document.getElementById("input-jeu");
    const proposition = input.value;

    if (!proposition) return;

    try {
        const res = await fetch(`${API_URL}/verifier-reponse`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ proposition: proposition })
        });

        const resultat = await res.json();
        const messageDiv = document.getElementById("message-resultat");

        if (resultat.victoire) {
            partieTerminee = true;
            messageDiv.innerHTML = `<span style="color: #4CAF50;">🎉 ${resultat.message}</span>`;
            if (player) player.pauseVideo();
            input.disabled = true;
            document.getElementById("btn-valider").disabled = true;
            
            sauvegarderProgression(true);
        } else {
            tentatives++;
            document.getElementById("texte-compteur").innerText = `Essais : ${tentatives} / ${MAX_TENTATIVES}`;
            input.value = ""; // On vide le champ
            
            if (tentatives >= MAX_TENTATIVES) {
                partieTerminee = true;
                messageDiv.innerHTML = `<span style="color: #f44336;">Bouboubou t'as pas trouver t'es vraiment trop nul reviens demain !</span>`;
                input.disabled = true;
                document.getElementById("btn-valider").disabled = true;
                if (player) player.pauseVideo();
                
                sauvegarderProgression(false);
            } else {
                messageDiv.innerHTML = `<span style="color: #f44336;">❌ ${resultat.message}</span>`;
                sauvegarderProgression(false);
            }
        }
    } catch (error) {
        console.error(error);
    }
});

// --- 4. GESTION DE LA BARRE DE PROGRESSION ---
let intervalProgression;

function formatTemps(secondes) {
    if (isNaN(secondes) || secondes < 0) return "0:00";
    const m = Math.floor(secondes / 60);
    const s = Math.floor(secondes % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function mettreAJourBarre() {
    if (player && typeof player.getCurrentTime === "function") {
        const currentTime = player.getCurrentTime();
        const duration = player.getDuration();
        if (duration > 0) {
            const pourcentage = (currentTime / duration) * 100;
            const barre = document.getElementById("barre-lecture");
            
            barre.value = pourcentage;
            document.getElementById("temps-actuel").innerText = formatTemps(currentTime);
            document.getElementById("temps-total").innerText = formatTemps(duration);
            
            // L'EFFET MAGIQUE : On remplit la barre en rouge au fur et à mesure !
            barre.style.background = `linear-gradient(to right, #ff0000 ${pourcentage}%, #334155 ${pourcentage}%)`;
        }
    }
}

// Si le joueur clique sur la barre pour avancer/reculer dans la musique
document.getElementById("barre-lecture").addEventListener("input", (e) => {
    if (player && typeof player.getDuration === "function") {
        const pourcentage = e.target.value;
        const duration = player.getDuration();
        const nouveauTemps = (pourcentage / 100) * duration;
        
        player.seekTo(nouveauTemps, true);
        document.getElementById("temps-actuel").innerText = formatTemps(nouveauTemps);
        e.target.style.background = `linear-gradient(to right, #ff0000 ${pourcentage}%, #334155 ${pourcentage}%)`;
    }
});

// On lance la machine
initialiserJeu();