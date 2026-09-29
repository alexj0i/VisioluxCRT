"""Scènes affichées sur le Visiolux — univers « abri antiatomique rétro ».

Pour ajouter ou modifier du texte, édite les scripts ci-dessous puis :
    sudo systemctl restart visiolux
"""
import datetime
import math
import os
import random

import numpy as np
from PIL import Image, ImageOps

from moteur import (ATTENUE, H, INVERSE, MX, MY, PAR, W, ZONE, Grille,
                    Lecteur, Terminal, attenuer, police)

ORGA = "NUCLEON SYSTEMES"
ABRI = "ABRI 42"
PROMPT = "ABRI42> "


class Scene:
    def demarrer(self, etat):
        pass

    def dessiner(self, img, d, t, dt, couleur):
        pass


class ScriptScene(Scene):
    """Scène « terminal » pilotée par un script (voir moteur.Lecteur)."""

    def __init__(self, script, taille=24, interligne=28):
        self.term = Terminal(taille, interligne)
        self.lect = Lecteur(self.term, script)

    def demarrer(self, etat):
        self.lect.reset()

    def dessiner(self, img, d, t, dt, couleur):
        self.lect.avancer(dt)
        self.term.dessiner(img, d, couleur, t)


# --------------------------------------------------------------------------
# 1. Démarrage
# --------------------------------------------------------------------------
def script_demarrage():
    yield ("pause", 0.8)
    yield ("taper", f"{ORGA} (R)\n", 40)
    yield ("taper", "MONITEUR BIOS V2.07 - 1977\n\n", 40)
    yield ("compter", "TEST MEMOIRE ....... {} KO", 0, 65536, 2.5)
    yield ("afficher", ATTENUE + "MEMOIRE OK\n")
    for p in ["LECTEUR DISQUE A", "LECTEUR BANDE", "HORLOGE", "CAPTEURS GEIGER", "RECYCLEUR D'AIR"]:
        yield ("taper", f"{p:.<26} ", 60)
        yield ("pause", random.uniform(0.2, 0.8))
        yield ("afficher", "OK\n")
    yield ("afficher", "\n")
    yield ("taper", "CHARGEMENT NUCLEON OS 4.1\n", 40)
    yield ("barre", "", 3.5)
    yield ("taper", f"CONNEXION RESEAU {ABRI} ... ", 40)
    yield ("pause", 1.2)
    yield ("afficher", "ETABLIE\n\n")
    yield ("taper", "BIENVENUE, SUPERVISEUR.\n", 25)
    yield ("afficher", PROMPT)
    yield ("pause", 8)


# --------------------------------------------------------------------------
# 2. Piratage du terminal
# --------------------------------------------------------------------------
MOTS = ["SERRURE", "CIRCUIT", "NEUTRON", "CAPSULE", "BUNKERS", "URANIUM",
        "ISOTOPE", "FISSION", "SIRENES", "TUNNELS", "CONSOLE", "BALISES"]
BRUIT = "!@#$%^&*()[]{}<>?/|;:'\",.-_=+"


def script_piratage():
    mots = random.sample(MOTS, 6)
    bon = mots[0]
    cell = ["".join(random.choice(BRUIT) for _ in range(12)) for _ in range(18)]
    for i, m in zip(random.sample(range(18), 6), mots):
        o = random.randint(0, 12 - len(m))
        cell[i] = cell[i][:o] + m + cell[i][o + len(m):]
    base = random.randrange(0xE000, 0xF000, 0x10)
    essais = 4

    def ligne_essais(n):
        return "ESSAIS RESTANTS : " + " ".join(["■"] * n)

    yield ("afficher", INVERSE + f" {ORGA} - TERMINAL PROTEGE\n")
    yield ("taper", "ENTREZ LE MOT DE PASSE\n", 30)
    yield ("afficher", ligne_essais(essais) + "\n\n")
    for r in range(9):
        yield ("taper", f"0x{base + r * 12:04X} {cell[r]}  0x{base + (r + 9) * 12:04X} {cell[r + 9]}\n", 400)
    yield ("afficher", "\n")                        # ligne de saisie = index 14
    for m in random.sample(mots[1:], random.randint(2, 3)) + [bon]:
        yield ("pause", 1.2)
        yield ("taper", "> " + m, 10)
        yield ("pause", 0.7)
        if m != bon:
            ok = sum(a == b for a, b in zip(m, bon))
            essais -= 1
            yield ("ligne", 14, f"> {m}  REFUSE  {ok}/7")
            yield ("ligne", 2, ligne_essais(essais))
            yield ("pause", 1.6)
            yield ("ligne", 14, "")
        else:
            yield ("ligne", 14, f"> {m}  ACCEPTE")
            yield ("pause", 1.5)
    yield ("effacer",)
    yield ("afficher", "\n\n\n\n\n")
    yield ("taper", INVERSE + "        ACCES AUTORISE\n\n", 30)
    yield ("taper", "     BIENVENUE, SUPERVISEUR.\n", 25)
    yield ("pause", 5)


# --------------------------------------------------------------------------
# 3. Console : commandes et réponses
# --------------------------------------------------------------------------
HABITANTS = ["DUPONT M.", "LEROY A.", "MOREAU J.", "FAURE C.", "GIRARD L.",
             "BLANC P.", "ROUX S.", "MARTIN E.", "LAMBERT G.", "BONNET R."]
POSTES = ["HYDROPONIE", "REACTEUR", "CUISINE", "INFIRMERIE", "SECURITE", "ECOLE", "ENTRETIEN"]
JOURNAL = ["FILTRE A AIR N.3 REMPLACE", "FUITE SECTEUR C REPAREE", "EXERCICE D'ALERTE : 4 MIN",
           "PLAINTE : RONFLEMENTS DORTOIR B", "RECOLTE TOMATES : 12 KG", "AMPOULE COULOIR 7 GRILLEE",
           "RADIO : AUCUN SIGNAL", "TOURNOI D'ECHECS : GIRARD L.", "PANNE MACHINE A CAFE"]


def commande(nom):
    r = random
    if nom == "DIAG REACTEUR":
        return [f"COEUR ............. {r.randint(395, 430)} C  NOMINAL",
                f"BARRES CONTROLE ... {r.randint(55, 70)} %",
                "REFROIDISSEMENT ... OK"]
    if nom == "METEO SURFACE":
        return [f"RADIATION EXT. .... {r.randint(300, 900)} mSv/h",
                f"TEMPERATURE ....... {r.randint(-8, 41)} C",
                "VISIBILITE ........ FAIBLE",
                ATTENUE + "SORTIE DECONSEILLEE"]
    if nom == "LISTE HABITANTS":
        return [f"B-{r.randint(1, 99):02d} {h:<11} {p}" for h, p in
                zip(r.sample(HABITANTS, 4), r.sample(POSTES, 4))]
    if nom == "JOURNAL":
        j = r.randint(900, 4000)
        return [f"J+{j + i:<5} {e}" for i, e in enumerate(r.sample(JOURNAL, 3))]
    if nom == "STOCK RATIONS":
        return [f"CONSERVES ......... {r.randint(2000, 9000)}",
                f"EAU (L) ........... {r.randint(20000, 60000)}",
                "CAFE .............. 0  !!!"]
    if nom == "PING SURFACE":
        return ["ENVOI SIGNAL ...", "ENVOI SIGNAL ...", "ENVOI SIGNAL ...", ATTENUE + "AUCUNE REPONSE"]
    return ["SAS PRINCIPAL ..... VERROUILLE", "JOINTS ............ OK",
            f"DERNIERE OUVERTURE  J+{r.randint(1, 900)}"]


def script_console():
    noms = ["DIAG REACTEUR", "METEO SURFACE", "LISTE HABITANTS", "JOURNAL",
            "STOCK RATIONS", "PING SURFACE", "STATUT PORTE"]
    yield ("afficher", INVERSE + f" {ORGA} - CONSOLE {ABRI}\n\n")
    while True:
        nom = random.choice(noms)
        yield ("afficher", PROMPT)
        yield ("pause", 0.8)
        yield ("taper", nom.lower(), 9)
        yield ("pause", 0.4)
        yield ("afficher", "\n")
        for l in commande(nom):
            yield ("pause", 0.8 if "SIGNAL" in l else 0.12)
            yield ("afficher", l + "\n")
        yield ("afficher", "\n")
        yield ("pause", 2.5)


# --------------------------------------------------------------------------
# 4. Porte blindée en ASCII (dessin original : trappe ronde à volant)
# --------------------------------------------------------------------------
class Porte(Scene):
    CYCLE = 26.0

    CARS = sorted(" .:/#@*-%o=~'")

    def __init__(self):
        self.grille = Grille(self.CARS, taille=11, cw=7, lh=11)
        self.cw, self.lh = 7, 11
        self.cars = np.array(self.CARS)
        self.fh = police(20)
        self.fb = police(22)
        self.cols = int((W - 2 * MX) // self.cw)
        self.rows = int((H - 2 * MY - 36 - 44) // self.lh)
        self.x0 = (W - self.cols * self.cw) / 2
        self.y0 = MY + 36
        c, r = np.meshgrid(np.arange(self.cols), np.arange(self.rows))
        self.cx = self.cols * self.cw / 2
        self.cy = self.rows * self.lh / 2
        self.rx = ((c + 0.5) * self.cw - self.cx) * PAR
        self.ry = (r + 0.5) * self.lh - self.cy
        self.r0 = np.hypot(self.rx, self.ry)
        self.R = R = 0.355 * self.rows * self.lh
        rx, ry, r0 = self.rx, self.ry, self.r0

        # Partie fixe : mur, encadrement, boulons, tunnel
        ch = np.full(r0.shape, " ", dtype="<U1")
        vif = np.zeros(r0.shape, dtype=bool)
        ch[(c + r) % 2 == 0] = "."
        bande = r >= self.rows - 3
        ch[bande] = np.where(((c - r) // 3) % 2 == 0, "/", " ")[bande]
        cadre = (r0 >= 1.02 * R) & (r0 <= 1.2 * R)
        ch[cadre], vif[cadre] = "#", True
        for k in range(12):
            a = k * math.pi / 6
            b = np.hypot(rx - 1.11 * R * math.cos(a), ry - 1.11 * R * math.sin(a)) < 0.045 * R
            ch[b], vif[b] = "@", True
        tun = r0 < 1.02 * R
        ch[tun] = " "
        for f in (0.82, 0.6, 0.42, 0.27):
            ch[tun & (np.abs(r0 - f * R) < 0.035 * R)] = ":"
        lum = r0 < 0.1 * R
        ch[lum], vif[lum] = "*", True
        self.fond_ch, self.fond_vif = ch, vif
        self.t0 = 0

    def demarrer(self, etat):
        self.t0 = None

    @staticmethod
    def _lisse(x):
        x = min(max(x, 0.0), 1.0)
        return x * x * (3 - 2 * x)

    def _phase(self, u):
        R = self.R
        if u < 3:
            return 0, 0, "PORTE VERROUILLEE", False
        if u < 8:
            return 4 * math.pi * self._lisse((u - 3) / 5), 0, "DEVERROUILLAGE", True
        if u < 10:
            return 4 * math.pi, 0, "EGALISATION PRESSION", True
        if u < 14:
            return 4 * math.pi, 2.1 * R * self._lisse((u - 10) / 4), "OUVERTURE", True
        if u < 19:
            return 4 * math.pi, 2.1 * R, f"BIENVENUE DANS L'{ABRI}", False
        if u < 23:
            return 4 * math.pi, 2.1 * R * (1 - self._lisse((u - 19) / 4)), "FERMETURE", True
        return 4 * math.pi * (1 - self._lisse((u - 23) / 3)), 0, "VERROUILLAGE", True

    def dessiner(self, img, d, t, dt, couleur):
        if self.t0 is None:
            self.t0 = t
        u = (t - self.t0) % self.CYCLE
        rot, dx, statut, clignote = self._phase(u)
        R = self.R
        rot += dx / R                      # la porte roule en s'ouvrant

        rx, ry, r0 = self.rx, self.ry, self.r0
        ch, vif = self.fond_ch.copy(), self.fond_vif.copy()

        # Vapeur pendant l'égalisation de pression
        if 8 <= u < 10:
            v = (r0 > 1.2 * R) & (r0 < 1.45 * R) & (np.random.rand(*r0.shape) < 0.3)
            ch[v] = np.random.choice(["~", "*", "'"], size=int(v.sum()))
            vif[v] = True

        # Porte
        px = rx - dx
        r1 = np.hypot(px, ry)
        ang = np.arctan2(ry, px) - rot
        porte = r1 < R
        ch[porte], vif[porte] = "-", False
        m = porte & (r1 >= 0.9 * R)
        ch[m], vif[m] = "%", True
        m = porte & (np.abs(r1 - 0.64 * R) < 0.03 * R)
        ch[m], vif[m] = "o", True
        m = porte & (r1 > 0.72 * R) & (r1 < 0.84 * R) & (np.cos(8 * ang) > 0.85)
        ch[m], vif[m] = "=", True
        m = porte & (np.abs(r1 - 0.42 * R) < 0.06 * R)
        ch[m], vif[m] = "#", True
        for k in range(3):
            a = rot + k * 2 * math.pi / 3
            le_long = px * math.cos(a) + ry * math.sin(a)
            travers = np.abs(-px * math.sin(a) + ry * math.cos(a))
            m = porte & (le_long > 0) & (r1 < 0.44 * R) & (travers < 0.07 * R)
            ch[m], vif[m] = "#", True
        m = porte & (r1 < 0.13 * R)
        ch[m], vif[m] = "@", True

        # Dessin
        codes = np.searchsorted(self.cars, ch)
        self.grille.dessiner(img, self.x0, self.y0, codes, np.where(vif, 1.0, 0.42), couleur)

        # En-tête et statut
        d.rectangle([MX - 4, MY, W - MX + 4, MY + 26], fill=couleur)
        d.text((MX + 4, MY + 2), f"{ABRI} - SAS PRINCIPAL", font=self.fh, fill=(0, 0, 0))
        heure = datetime.datetime.now().strftime("%H:%M:%S")
        d.text((W - MX - self.fh.getlength(heure) - 4, MY + 2), heure, font=self.fh, fill=(0, 0, 0))
        if not clignote or int(t * 2) % 2 == 0:
            larg = self.fb.getlength(statut)
            d.text(((W - larg) / 2, H - MY - 32), statut, font=self.fb, fill=couleur)


# --------------------------------------------------------------------------
# 5. Moniteur de l'abri
# --------------------------------------------------------------------------
class Moniteur(Scene):
    def __init__(self):
        self.f = police(22)
        self.fs = police(18)
        self.v = {"rad": 0.2, "temp": 412.0, "o2": 20.9, "eau": 87.0}
        self.hist = [0.2] * 120
        self.acc = 0
        self.clic = 0

    def dessiner(self, img, d, t, dt, couleur):
        v = self.v
        faible = attenuer(couleur, 0.45)
        # évolution des mesures
        v["temp"] = min(440, max(390, v["temp"] + random.gauss(0, 6) * dt))
        v["o2"] = min(21.3, max(20.2, v["o2"] + random.gauss(0, 0.2) * dt))
        v["eau"] = min(99, max(60, v["eau"] + random.gauss(0, 0.5) * dt))
        cible = 0.2 + (random.random() < 0.02) * random.uniform(1, 3.5)
        v["rad"] = max(0.05, v["rad"] + (cible - v["rad"]) * min(1, 3 * dt) + random.gauss(0, 0.03))
        self.acc += dt
        if self.acc > 0.25:
            self.acc = 0
            self.hist = self.hist[1:] + [v["rad"]]
        if random.random() < v["rad"] * dt * 4:
            self.clic = 0.12
        self.clic -= dt

        x0, x1 = MX, W - MX
        d.rectangle([x0 - 4, MY, x1 + 4, MY + 30], fill=couleur)
        d.text((x0 + 4, MY + 3), f"SURVEILLANCE {ABRI}", font=self.f, fill=(0, 0, 0))
        now = datetime.datetime.now()
        h = now.strftime("%H:%M:%S")
        d.text((x1 - self.f.getlength(h) - 4, MY + 3), h, font=self.f, fill=(0, 0, 0))
        jours = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        d.text((x0, MY + 38), f"{jours[now.weekday()]} {now:%d/%m/%Y}   POPULATION : 104", font=self.fs, fill=faible)

        lignes = [("RADIATION", f"{v['rad']:.2f} mSv/h", v["rad"] / 4),
                  ("REACTEUR", f"{v['temp']:.0f} C", (v["temp"] - 350) / 120),
                  ("OXYGENE", f"{v['o2']:.1f} %", (v["o2"] - 19) / 3),
                  ("EAU POTABLE", f"{v['eau']:.0f} %", v["eau"] / 100)]
        y = MY + 70
        for nom, val, frac in lignes:
            d.text((x0, y), nom, font=self.f, fill=couleur)
            d.text((x0 + 175, y), val, font=self.f, fill=couleur)
            bx = x0 + 360
            d.rectangle([bx, y + 4, x1, y + 24], outline=couleur, width=2)
            d.rectangle([bx + 4, y + 8, bx + 4 + (x1 - bx - 8) * min(max(frac, 0), 1), y + 20], fill=couleur)
            y += 40

        # graphe du compteur Geiger
        gy0, gy1 = y + 14, H - MY - 6
        d.text((x0, gy0 - 4), "COMPTEUR GEIGER - 30 S", font=self.fs, fill=faible)
        if self.clic > 0:
            d.text((x1 - 90, gy0 - 4), "* CLIC", font=self.fs, fill=couleur)
        gy0 += 22
        d.rectangle([x0, gy0, x1, gy1], outline=couleur, width=2)
        n = len(self.hist)
        pts = [(x0 + 4 + i * (x1 - x0 - 8) / (n - 1),
                gy1 - 6 - min(r / 4, 1) * (gy1 - gy0 - 12)) for i, r in enumerate(self.hist)]
        d.line(pts, fill=couleur, width=3)
        if v["rad"] > 1.5 and int(t * 3) % 2 == 0:
            d.rectangle([x0 + 10, gy0 + 8, x0 + 140, gy0 + 36], fill=couleur)
            d.text((x0 + 18, gy0 + 10), "ALERTE", font=self.f, fill=(0, 0, 0))


# --------------------------------------------------------------------------
# 6. Message, image, veille, arrêt
# --------------------------------------------------------------------------
class Message(ScriptScene):
    def __init__(self):
        self.message = ""
        super().__init__(self._script)

    def _script(self):
        yield ("afficher", ATTENUE + ">> MESSAGE RECU\n\n")
        yield ("pause", 0.8)
        yield ("taper", self.message or "(AUCUN MESSAGE)", 16)
        yield ("pause", 40)

    def demarrer(self, etat):
        self.message = etat.get("message", "").upper()
        super().demarrer(etat)


class ImageScene(Scene):
    def __init__(self, chemin):
        self.chemin = chemin
        self.cache = (None, None, None)
        self.f = police(22)

    def dessiner(self, img, d, t, dt, couleur):
        try:
            mtime = os.path.getmtime(self.chemin)
        except OSError:
            d.text((MX, H / 2 - 30), "AUCUNE IMAGE", font=self.f, fill=couleur)
            d.text((MX, H / 2 + 5), "ENVOIE-EN UNE DEPUIS LA PAGE WEB", font=self.f,
                   fill=attenuer(couleur, 0.5))
            return
        if self.cache[:2] != (mtime, couleur):
            gris = Image.open(self.chemin).convert("L")
            self.cache = (mtime, couleur, ImageOps.colorize(gris, (0, 0, 0), couleur))
        img.paste(self.cache[2], (0, 0))


def preparer_image(fichier, sortie):
    """Convertit une image envoyée en 720x576 niveaux de gris, cadrée dans la
    zone visible et corrigée du rapport des pixels PAL."""
    im = ImageOps.exif_transpose(Image.open(fichier)).convert("L")
    lz, hz = ZONE[2] - ZONE[0], ZONE[3] - ZONE[1]
    im = im.resize((max(1, round(im.width / PAR)), im.height))
    im.thumbnail((lz, hz), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=1)
    fond = Image.new("L", (W, H), 0)
    fond.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    fond.save(sortie)


class Veille(Scene):
    pass


def script_arret():
    yield ("afficher", "\n\n\n\n")
    yield ("taper", "ARRET DU SYSTEME EN COURS\n\n", 30)
    yield ("barre", "", 2.5)
    yield ("taper", "\nATTENDS 20 S AVANT DE DEBRANCHER\n", 30)
    yield ("pause", 999)


def script_redemarrage():
    yield ("afficher", "\n\n\n\n")
    yield ("taper", "REDEMARRAGE EN COURS\n\n", 30)
    yield ("barre", "", 2.5)
    yield ("pause", 999)


# --------------------------------------------------------------------------
# Registre : nom interne -> (libellé pour la page web, scène)
# --------------------------------------------------------------------------
def creer_scenes(chemin_image):
    return {
        "demarrage": ("Démarrage", ScriptScene(script_demarrage)),
        "porte": ("Porte blindée", Porte()),
        "piratage": ("Piratage", ScriptScene(script_piratage)),
        "moniteur": ("Moniteur", Moniteur()),
        "console": ("Console", ScriptScene(script_console)),
        "message": ("Message", Message()),
        "image": ("Image", ImageScene(chemin_image)),
        "veille": ("Écran noir", Veille()),
        "_arret": ("", ScriptScene(script_arret)),
        "_redemarrage": ("", ScriptScene(script_redemarrage)),
    }


ROTATION = ["demarrage", "porte", "piratage", "moniteur", "console"]
